from pathlib import Path
from typing import List

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics

from config import THUMB_SIZE
from ui.tag_display import ReadOnlyTagsContainer
from utils.image_utils import load_thumbnail


class ImageGridView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._container = QWidget()
        self._hbox = QHBoxLayout(self._container)
        self._hbox.setContentsMargins(4, 4, 4, 4)
        self._hbox.setSpacing(4)

        self.setWidget(self._container)
        self.setWidgetResizable(False)
        self.setMinimumHeight(THUMB_SIZE + 60)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._show_empty()

    def load_from_bus(self, bus, task_id: str):
        old = self.widget()
        if old is not None:
            self.setWidget(None)
            old.deleteLater()

        self._container = QWidget()
        self._hbox = QHBoxLayout(self._container)
        self._hbox.setContentsMargins(4, 4, 4, 4)
        self._hbox.setSpacing(4)

        if not bus or not task_id:
            self._show_empty()
            self.setWidget(self._container)
            return

        task = bus.get_task(task_id)
        if not task or not task.images:
            self._show_empty()
            self.setWidget(self._container)
            return

        for p in task.images:
            pixmap = load_thumbnail(p, THUMB_SIZE)
            if pixmap is None or pixmap.isNull():
                continue

            item_widget = QWidget()
            item_widget.setFixedWidth(THUMB_SIZE)
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(2)

            img_label = QLabel()
            img_label.setPixmap(pixmap)
            img_label.setFixedSize(pixmap.width(), pixmap.height())
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(img_label, 0, Qt.AlignmentFlag.AlignCenter)

            name_label = QLabel()
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fm = QFontMetrics(name_label.font())
            elided = fm.elidedText(p.name, Qt.TextElideMode.ElideMiddle, THUMB_SIZE - 4)
            name_label.setText(elided)
            name_label.setToolTip(p.name)
            item_layout.addWidget(name_label)

            self._hbox.addWidget(item_widget)

        self._hbox.addStretch()

        self._container.adjustSize()
        self.setWidget(self._container)
        self.horizontalScrollBar().setValue(0)

    def clear(self):
        self.load_from_bus(None, "")

    def _show_empty(self):
        label = QLabel("No images")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(300, 200)
        self._hbox.addWidget(label)


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = None
        self._current_task_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._image_preview = ImageGridView()
        layout.addWidget(self._image_preview)

        self._tag_display = ReadOnlyTagsContainer()
        layout.addWidget(self._tag_display, stretch=1)

    def set_bus(self, bus):
        if self._bus:
            self._bus.task_selection_changed.disconnect(self._on_selection_changed)
            self._bus.task_state_changed.disconnect(self._on_state_changed)
        self._bus = bus
        if bus:
            bus.task_selection_changed.connect(self._on_selection_changed)
            bus.task_state_changed.connect(self._on_state_changed)

    def _on_selection_changed(self, task_id: str):
        self._current_task_id = task_id
        self._image_preview.load_from_bus(self._bus, task_id)
        self._refresh_tags()

    def _on_state_changed(self, task_id: str, old_state: int, new_state: int):
        if task_id == self._current_task_id:
            self._refresh_tags()

    def _refresh_tags(self):
        if not self._bus or not self._current_task_id:
            self._tag_display.clear()
            return

        task = self._bus.get_task(self._current_task_id)
        if task and task.tag_data:
            all_tags = []
            for tg in task.tag_data.tags.values():
                all_tags.extend(tg)
            self._tag_display.load_tags(all_tags, None)
        else:
            self._tag_display.clear()

    def clear(self):
        self._current_task_id = ""
        self._image_preview.clear()
        self._tag_display.clear()
