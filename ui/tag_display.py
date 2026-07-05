from typing import Dict, List, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont

from config import ALL_TAG_CATEGORIES
from kernel.models import AITag, PresetTagSet
from kernel.prompt_service import PresetService
from ui.flow_layout import FlowLayout


class ReadOnlyTagPanel(QWidget):

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self._category = category
        self._tags: List[AITag] = []
        self._preset: Optional[PresetTagSet] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        self._title = QLabel(category.capitalize())
        font = QFont()
        font.setBold(True)
        self._title.setFont(font)
        layout.addWidget(self._title)

        self._flow_widget = QWidget()
        self._flow = FlowLayout(self._flow_widget, margin=0, spacing=4)
        layout.addWidget(self._flow_widget)

        self.setVisible(False)

    def load_tags(self, tags: List[AITag], preset: Optional[PresetTagSet] = None):
        self._tags = [t for t in tags if t.category == self._category]
        self._preset = preset
        self._rebuild()
        self.setVisible(len(self._tags) > 0)

    def _resolve_name(self, tag: AITag) -> str:
        return PresetService.resolve_tag_name(self._preset, tag.category, tag.value)

    def _rebuild(self):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for tag in self._tags:
            display_name = self._resolve_name(tag)
            label = QLabel(f"{display_name} {tag.confidence:.2f}")
            label.setStyleSheet(
                "background: #e0e7ff; color: #1e3a5f; border: 1px solid #93c5fd; "
                "border-radius: 4px; padding: 2px 6px; font-size: 12px;"
            )
            self._flow.addWidget(label)


class ReadOnlyTagsContainer(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: Dict[str, ReadOnlyTagPanel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for cat in ALL_TAG_CATEGORIES:
            panel = ReadOnlyTagPanel(cat)
            layout.addWidget(panel)
            self._panels[cat] = panel

        layout.addStretch()

    def load_tags(self, tags: List[AITag], preset: Optional[PresetTagSet] = None):
        for cat in ALL_TAG_CATEGORIES:
            self._panels[cat].load_tags(tags, preset)

    def clear(self):
        for cat in ALL_TAG_CATEGORIES:
            self._panels[cat].load_tags([])
