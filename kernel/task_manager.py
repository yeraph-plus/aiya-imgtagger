import asyncio
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker

from config import AGENT_WORKER_COUNT
from kernel.models import Task, TaskState, FolderTagData, PresetTagSet
from kernel.agent import AIAgentClient
from kernel.storage import Storage

_ACTIVE_STATES = (
    TaskState.QUEUED, TaskState.PRELOADED, TaskState.PRELOADING,
    TaskState.LOADED, TaskState.PROCESSING,
)
_PENDING_DEQUEUE_STATES = (TaskState.PRELOADED, TaskState.QUEUED)


class AgentWorker(QThread):
    task_done = pyqtSignal(str, bool, str)
    folder_completed = pyqtSignal(str)

    def __init__(self, task_manager, model: str, preset: Optional[PresetTagSet] = None):
        super().__init__()
        self._tm = task_manager
        self._model = model
        self._preset = preset
        self._cancelled = False

    def run(self):
        try:
            asyncio.run(self._run_all())
        except Exception:
            pass
        self.task_done.emit("", True, "")  # sentinel: worker exited

    def cancel(self):
        self._cancelled = True

    async def _run_all(self):
        bus = self._tm._bus
        async with AIAgentClient(self._model) as client:
            while not self._cancelled:
                task = self._tm.dequeue_task()
                if task is None:
                    break

                bus.set_task_state(task.id, TaskState.PROCESSING)

                if Storage.has_tags(task.path):
                    tag_data = Storage.load_tags(task.path)
                    bus.set_task_state(task.id, TaskState.COMPLETED, tag_data=tag_data)
                    self.folder_completed.emit(f"{task.name} (skipped)")
                    self.task_done.emit(task.id, True, "")
                    continue

                if self._cancelled:
                    bus.set_task_state(task.id, TaskState.QUEUED)
                    break

                try:
                    tags = await client.analyze_folder(task.images, preset=self._preset)

                    if self._cancelled:
                        bus.set_task_state(task.id, TaskState.QUEUED)
                        break

                    if not tags:
                        error_msg = "API returned no valid tags. ai_tags.json not created."
                        bus.set_task_state(task.id, TaskState.ERROR, error_message=error_msg)
                        self.folder_completed.emit(task.name)
                        self.task_done.emit(task.id, False, error_msg)
                        continue

                    tag_data = FolderTagData()
                    for tag in tags:
                        tag_data.tags[tag.category].append(tag)
                    Storage.save_tags(task.path, tag_data)
                    bus.set_task_state(task.id, TaskState.COMPLETED, tag_data=tag_data)
                    self.folder_completed.emit(task.name)
                    self.task_done.emit(task.id, True, "")
                except Exception as e:
                    error_msg = str(e)
                    if self._cancelled:
                        bus.set_task_state(task.id, TaskState.QUEUED)
                        break
                    bus.set_task_state(task.id, TaskState.ERROR, error_message=error_msg)
                    self.folder_completed.emit(task.name)
                    self.task_done.emit(task.id, False, error_msg)


class TaskManager(QObject):
    progress = pyqtSignal(int, int)
    folder_completed = pyqtSignal(str)
    folder_error = pyqtSignal(str, str)
    finished = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, bus, model: str, preset: Optional[PresetTagSet] = None):
        super().__init__()
        self._bus = bus
        self._model = model
        self._preset = preset
        self._workers: list[AgentWorker] = []
        self._mutex = QMutex()
        self._cancelled = False
        self._total = 0
        self._completed_count = 0
        self._active_workers = 0
        self._finished_emitted = False

    def dequeue_task(self) -> Optional[Task]:
        with QMutexLocker(self._mutex):
            if self._cancelled:
                return None
            for task in self._bus.get_all_tasks():
                if task.state in _PENDING_DEQUEUE_STATES:
                    task_id = task.id
                    break
            else:
                return None
        self._bus.set_task_state(task_id, TaskState.QUEUED)
        return self._bus.get_task(task_id)

    def start(self):
        tasks = self._bus.get_all_tasks()
        self._total = sum(1 for t in tasks if t.state not in (TaskState.COMPLETED, TaskState.ERROR)
                          and not Storage.has_tags(t.path))

        for task in tasks:
            if task.state == TaskState.PRELOADED:
                self._bus.set_task_state(task.id, TaskState.QUEUED)

        worker_count = max(1, AGENT_WORKER_COUNT)
        self._active_workers = worker_count
        for i in range(worker_count):
            worker = AgentWorker(self, self._model, self._preset)
            worker.task_done.connect(self._on_task_done)
            worker.folder_completed.connect(self.folder_completed)
            worker.finished.connect(worker.deleteLater)
            worker.start()
            self._workers.append(worker)

    def _on_task_done(self, task_id: str, success: bool, error: str):
        if task_id:
            self._completed_count += 1
            self.progress.emit(self._completed_count, max(self._total, self._completed_count))

            task = self._bus.get_task(task_id)
            task_name = task.name if task else task_id
            if not success and error:
                self.folder_error.emit(task_name, error)

        with QMutexLocker(self._mutex):
            self._active_workers -= 1
            if self._active_workers < 0:
                self._active_workers = 0
            should_finish = self._active_workers == 0 or self._cancelled
            if should_finish and self._finished_emitted:
                should_finish = False

        if should_finish:
            self._finished_emitted = True
            self.finished.emit()

    def cancel(self):
        with QMutexLocker(self._mutex):
            if self._cancelled:
                return
            self._cancelled = True
        for worker in self._workers:
            if worker.isRunning():
                worker.cancel()
        for worker in self._workers:
            if worker.isRunning():
                worker.wait(2000)
        self.cancelled.emit()
        if self._active_workers == 0 and not self._finished_emitted:
            self._finished_emitted = True
            self.finished.emit()

    def get_total(self) -> int:
        return self._total

    def get_completed(self) -> int:
        return self._completed_count
