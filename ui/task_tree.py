from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal

from kernel.models import TaskState, TASK_STATE_LABELS


class TaskTreeWidget(QTreeWidget):
    task_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = None

        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self.itemClicked.connect(self._on_item_clicked)

    def set_bus(self, bus):
        if self._bus:
            self._bus.task_state_changed.disconnect(self._on_task_state_changed)
            self._bus.all_tasks_updated.disconnect(self._rebuild)
        self._bus = bus
        if bus:
            bus.task_state_changed.connect(self._on_task_state_changed)
            bus.all_tasks_updated.connect(self._rebuild)
        self._rebuild()

    def _rebuild(self):
        self.clear()
        if not self._bus:
            return

        for task in self._bus.get_all_tasks():
            item = QTreeWidgetItem()
            label = TASK_STATE_LABELS.get(task.state, "[..]")
            item.setText(0, f"{label} {task.name}")
            item.setData(0, Qt.ItemDataRole.UserRole, task.id)
            self.addTopLevelItem(item)

    def _on_task_state_changed(self, task_id: str, old_state: int, new_state: int):
        count = self.topLevelItemCount()
        for i in range(count):
            item = self.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == task_id:
                new_state_enum = TaskState(new_state)
                label = TASK_STATE_LABELS.get(new_state_enum, "[..]")
                task = self._bus.get_task(task_id) if self._bus else None
                name = task.name if task else ""
                item.setText(0, f"{label} {name}")
                return

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        task_id = item.data(0, Qt.ItemDataRole.UserRole)
        if task_id and self._bus:
            self._bus.select_task(task_id)
            self.task_selected.emit(task_id)

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        task_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not task_id:
            return

        task = self._bus.get_task(task_id) if self._bus else None

        menu = QMenu(self)
        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(lambda: self._bus.refresh() if self._bus else None)

        if task and task.state == TaskState.ERROR:
            retry_action = menu.addAction("Retry")
            retry_action.triggered.connect(lambda: self._bus.set_task_state(task_id, TaskState.PRELOADED) if self._bus else None)

        menu.exec(self.viewport().mapToGlobal(pos))
