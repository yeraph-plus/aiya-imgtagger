from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from config import PRELOAD_TASK_COUNT
from kernel.models import Task, TaskState
from kernel.scanner import scan_entry, scan_images
from kernel.storage import Storage
from kernel.info_service import InfoService
from utils.image_utils import load_pixmap, THUMB_SIZE


class _PreloadWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, task_id, images):
        super().__init__()
        self._task_id = task_id
        self._images = images

    def run(self):
        for img_path in self._images:
            try:
                with open(img_path, "rb") as f:
                    f.read()
            except Exception:
                pass
        self.done.emit(self._task_id)


class DataBus(QObject):
    task_state_changed = pyqtSignal(str, int, int)
    task_preloaded = pyqtSignal(str)
    task_selection_changed = pyqtSignal(str)
    all_tasks_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: Dict[str, Task] = OrderedDict()
        self._entry_path: Optional[Path] = None
        self._selected_task_id: str = ""
        self._thumbnail_cache: Dict[str, Dict[str, QPixmap]] = {}
        self._preload_count: int = PRELOAD_TASK_COUNT
        self._preload_workers: list = []

    def set_preload_count(self, count: int):
        self._preload_count = max(1, count)

    def get_preload_count(self) -> int:
        return self._preload_count

    @property
    def entry_path(self) -> Optional[Path]:
        return self._entry_path

    @property
    def selected_task_id(self) -> str:
        return self._selected_task_id

    def load_entry(self, path: Path):
        self._stop_preload_workers()
        self._tasks.clear()
        self._thumbnail_cache.clear()
        self._selected_task_id = ""
        self._entry_path = path

        folders = scan_entry(path)
        for folder in sorted(folders):
            task = Task(
                id=str(folder),
                path=folder,
                name=folder.name,
                state=TaskState.UNLOADED,
            )
            self._tasks[task.id] = task

        self.all_tasks_updated.emit()

        QThread.msleep(50)
        self._start_scanning()

    def _start_scanning(self):
        for task in self._tasks.values():
            if task.state == TaskState.UNLOADED:
                self._set_task_state(task.id, TaskState.SCANNING)
                images = scan_images(task.path)
                task.images = images

                has_tags = Storage.has_tags(task.path)
                if has_tags:
                    tag_data = Storage.load_tags(task.path)
                    if tag_data:
                        task.tag_data = tag_data

                info_data = InfoService.load(task.path)
                if info_data:
                    task.info = info_data

                if has_tags and task.tag_data:
                    self._set_task_state(task.id, TaskState.COMPLETED, tag_data=task.tag_data)
                else:
                    self._set_task_state(task.id, TaskState.LOADED)

        self._start_preloading()

    def _start_preloading(self):
        preload_count = 0
        for task in self._tasks.values():
            if task.state == TaskState.LOADED:
                if preload_count < self._preload_count:
                    self._set_task_state(task.id, TaskState.PRELOADING)
                    self._preload_task(task)
                    preload_count += 1

    def _preload_task(self, task: Task):
        worker = _PreloadWorker(task.id, task.images)
        worker.done.connect(self._on_preload_done)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._preload_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        try:
            self._preload_workers.remove(worker)
        except ValueError:
            pass

    def _stop_preload_workers(self):
        for worker in self._preload_workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)
        self._preload_workers.clear()

    def _on_preload_done(self, task_id: str):
        task = self._tasks.get(task_id)
        if task and task.state == TaskState.PRELOADING:
            self._set_task_state(task_id, TaskState.PRELOADED)
            self.task_preloaded.emit(task_id)
            self._start_preloading()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self._tasks.values())

    def get_tasks_by_state(self, state: TaskState) -> List[Task]:
        return [t for t in self._tasks.values() if t.state == state]

    def select_task(self, task_id: str):
        if task_id == self._selected_task_id:
            return
        self._selected_task_id = task_id
        self.task_selection_changed.emit(task_id)

    def get_thumbnail(self, task_id: str, image_index: int = 0) -> Optional[QPixmap]:
        task = self._tasks.get(task_id)
        if not task or image_index >= len(task.images):
            return None
        return load_pixmap(task.images[image_index], THUMB_SIZE, THUMB_SIZE)

    def get_all_thumbnails(self, task_id: str) -> List[QPixmap]:
        task = self._tasks.get(task_id)
        if not task:
            return []
        thumbs = []
        for img_path in task.images:
            pix = load_pixmap(img_path, THUMB_SIZE, THUMB_SIZE)
            if pix and not pix.isNull():
                thumbs.append(pix)
        return thumbs

    def get_task_count(self) -> int:
        return len(self._tasks)

    def get_pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.state in
                   (TaskState.UNLOADED, TaskState.SCANNING, TaskState.LOADED,
                    TaskState.PRELOADING, TaskState.PRELOADED, TaskState.QUEUED))

    def get_completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.state == TaskState.COMPLETED)

    def get_error_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.state == TaskState.ERROR)

    def set_task_state(self, task_id: str, new_state: TaskState, **kwargs):
        self._set_task_state(task_id, new_state, **kwargs)

    def _set_task_state(self, task_id: str, new_state: TaskState, **kwargs):
        task = self._tasks.get(task_id)
        if not task:
            return
        old_state = task.state
        task.state = new_state

        if "error_message" in kwargs:
            task.error_message = kwargs["error_message"]
        if "tag_data" in kwargs:
            task.tag_data = kwargs["tag_data"]

        self.task_state_changed.emit(task_id, old_state.value, new_state.value)

    def refresh(self):
        if self._entry_path:
            self._thumbnail_cache.clear()
            self.load_entry(self._entry_path)

    def shutdown(self):
        self._stop_preload_workers()
