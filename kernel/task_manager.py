import asyncio
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker

from config import AGENT_WORKER_COUNT
from kernel.models import Task, TaskState, FolderTagData, PresetTagSet
from kernel.agent import AIAgentClient
from kernel.storage import Storage


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
        asyncio.run(self._run_all())

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

                try:
                    tags = await client.analyze_folder(task.images, preset=self._preset)

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

    def dequeue_task(self) -> Optional[Task]:
        with QMutexLocker(self._mutex):
            for task in self._bus.get_all_tasks():
                if task.state in (TaskState.PRELOADED, TaskState.QUEUED):
                    self._bus.set_task_state(task.id, TaskState.QUEUED)
                    return task
            return None

    def start(self):
        tasks = self._bus.get_all_tasks()
        self._total = sum(1 for t in tasks if t.state not in (TaskState.COMPLETED, TaskState.ERROR)
                          and not Storage.has_tags(t.path))

        for task in tasks:
            if task.state == TaskState.PRELOADED:
                self._bus.set_task_state(task.id, TaskState.QUEUED)

        for i in range(AGENT_WORKER_COUNT):
            worker = AgentWorker(self, self._model, self._preset)
            worker.task_done.connect(self._on_task_done)
            worker.folder_completed.connect(self.folder_completed)
            worker.start()
            self._workers.append(worker)

    def _on_task_done(self, task_id: str, success: bool, error: str):
        self._completed_count += 1
        self.progress.emit(self._completed_count, self._total)

        task = self._bus.get_task(task_id)
        task_name = task.name if task else task_id
        if not success and error:
            self.folder_error.emit(task_name, error)

        all_done = True
        for task in self._bus.get_all_tasks():
            if task.state in (TaskState.QUEUED, TaskState.PRELOADED, TaskState.PRELOADING,
                              TaskState.LOADED, TaskState.PROCESSING):
                all_done = False
                break

        if all_done:
            self.finished.emit()

    def cancel(self):
        self._cancelled = True
        for worker in self._workers:
            if worker.isRunning():
                worker.cancel()
                worker.wait(1000)
        self.cancelled.emit()

    def get_total(self) -> int:
        return self._total

    def get_completed(self) -> int:
        return self._completed_count
