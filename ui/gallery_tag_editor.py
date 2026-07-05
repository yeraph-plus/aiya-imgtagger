from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QPushButton, QFormLayout,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config import ALL_TAG_CATEGORIES, CONSTRAINED_CATEGORIES, GALLERY_CATEGORIES
from kernel.models import PresetTagSet
from kernel.info_service import GalleryInfo
from kernel.prompt_service import PresetService
from ui.flow_layout import FlowLayout

if TYPE_CHECKING:
    from kernel.models import FolderTagData


class _CategoryTagPanel(QWidget):
    modified = pyqtSignal()
    unknown_tag_checked = pyqtSignal(str, str)

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self._category = category
        self._checkbox_map: Dict[str, QCheckBox] = {}
        self._unknown_checkbox_map: Dict[str, QCheckBox] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(4)

        title = QLabel(category.capitalize())
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        self._checkbox_widget = QWidget()
        self._checkbox_flow = FlowLayout(self._checkbox_widget, margin=0, spacing=4)
        main_layout.addWidget(self._checkbox_widget)

        self._unknown_label = QLabel("Other AI Tags:")
        self._unknown_label.setVisible(False)
        main_layout.addWidget(self._unknown_label)

        self._unknown_widget = QWidget()
        self._unknown_flow = FlowLayout(self._unknown_widget, margin=0, spacing=4)
        self._unknown_widget.setVisible(False)
        main_layout.addWidget(self._unknown_widget)

    def load_checkboxes(self, items: List[Tuple[str, str, bool]]):
        self._checkbox_map.clear()
        while self._checkbox_flow.count():
            item = self._checkbox_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for slug, name, checked in items:
            cb = QCheckBox(name)
            cb.setToolTip(slug)
            cb.setChecked(checked)
            cb.toggled.connect(lambda c, s=slug: self._on_toggle(s, c))
            self._checkbox_map[slug] = cb
            self._checkbox_flow.addWidget(cb)

    def load_unknown(self, items: List[Tuple[str, str]]):
        self._unknown_checkbox_map.clear()
        while self._unknown_flow.count():
            item = self._unknown_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_items = len(items) > 0
        self._unknown_label.setVisible(has_items)
        self._unknown_widget.setVisible(has_items)

        for slug, name in items:
            cb = QCheckBox(name)
            cb.setToolTip(slug)
            cb.setChecked(False)
            cb.setStyleSheet("color: #888888;")
            cb.toggled.connect(lambda c, s=slug: self._on_unknown_toggle(s, c))
            self._unknown_checkbox_map[slug] = cb
            self._unknown_flow.addWidget(cb)

    def get_checked(self) -> List[str]:
        slugs = sorted(slug for slug, cb in self._checkbox_map.items() if cb.isChecked())
        slugs += sorted(slug for slug, cb in self._unknown_checkbox_map.items() if cb.isChecked())
        return slugs

    def _on_toggle(self, slug: str, checked: bool):
        self.modified.emit()

    def _on_unknown_toggle(self, slug: str, checked: bool):
        if checked:
            self.unknown_tag_checked.emit(self._category, slug)
        self.modified.emit()


class GalleryTagEditor(QWidget):
    modified = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: Dict[str, _CategoryTagPanel] = {}
        self._current_preset: Optional[PresetTagSet] = None
        self._original_file_count: dict = {"image": 0, "video": 0}
        self._original_file_size: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        meta_widget = QWidget()
        meta_form = QFormLayout(meta_widget)
        meta_form.setSpacing(4)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Gallery title")
        meta_form.addRow("Title:", self._title_input)

        category_radio_widget = QWidget()
        category_radio_layout = QHBoxLayout(category_radio_widget)
        category_radio_layout.setContentsMargins(0, 0, 0, 0)
        category_radio_layout.setSpacing(12)
        category_radio_layout.addStretch()
        self._category_group = QButtonGroup(self)
        self._category_radios: Dict[str, QRadioButton] = {}
        for cat_key in GALLERY_CATEGORIES:
            rb = QRadioButton(cat_key.capitalize())
            self._category_group.addButton(rb)
            category_radio_layout.addWidget(rb)
            self._category_radios[cat_key] = rb
            rb.toggled.connect(lambda c, k=cat_key: self._on_category_toggled(k, c))
        meta_form.addRow("Category:", category_radio_widget)

        self._language_input = QLineEdit()
        self._language_input.setPlaceholderText("Language")
        meta_form.addRow("Language:", self._language_input)

        file_count_widget = QWidget()
        file_count_layout = QHBoxLayout(file_count_widget)
        file_count_layout.setContentsMargins(0, 0, 0, 0)
        file_count_layout.setSpacing(8)
        file_count_layout.addWidget(QLabel("Images:"))
        self._image_count_label = QLabel("0")
        file_count_layout.addWidget(self._image_count_label)
        file_count_layout.addWidget(QLabel("Videos:"))
        self._video_count_label = QLabel("0")
        file_count_layout.addWidget(self._video_count_label)
        file_count_layout.addStretch()
        meta_form.addRow("File Count:", file_count_widget)

        self._file_size_label = QLabel("0 bytes")
        meta_form.addRow("File Size:", self._file_size_label)

        layout.addWidget(meta_widget)

        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setContentsMargins(4, 4, 4, 4)
        tags_layout.setSpacing(2)

        for cat in ALL_TAG_CATEGORIES:
            panel = _CategoryTagPanel(cat)
            panel.modified.connect(self._on_panel_modified)
            panel.unknown_tag_checked.connect(self._on_unknown_tag_checked)
            tags_layout.addWidget(panel)
            self._panels[cat] = panel

        layout.addWidget(tags_widget)

    def _on_panel_modified(self):
        self.modified.emit()

    def _on_category_toggled(self, key: str, checked: bool):
        self.modified.emit()

    def _on_unknown_tag_checked(self, category: str, slug: str):
        if self._current_preset:
            name = slug.replace("_", " ").title()
            PresetService.add_tag(self._current_preset, category, slug, name)
            PresetService.save(self._current_preset)

    def load_project(self, ai_tags: Optional["FolderTagData"], info: Optional[GalleryInfo], preset: Optional[PresetTagSet] = None):
        self._current_preset = preset

        if ai_tags is None and info is None:
            for panel in self._panels.values():
                panel.load_checkboxes([])
                panel.load_unknown([])
            self._clear_form()
            return

        ai_conf_map: Dict[str, Dict[str, float]] = {cat: {} for cat in ALL_TAG_CATEGORIES}
        if ai_tags:
            for cat in ALL_TAG_CATEGORIES:
                for t in ai_tags.tags.get(cat, []):
                    if t.value:
                        ai_conf_map[cat][t.value] = t.confidence

        info_slugs: Dict[str, Set[str]] = {
            cat: set(info.tags.get(cat, [])) if info else set()
            for cat in ALL_TAG_CATEGORIES
        }

        def resolve_name(cat: str, slug: str) -> str:
            if preset:
                for pt in preset.groups.get(cat, []):
                    if pt.slug == slug:
                        return pt.name
            return slug.replace("_", " ").title()

        preset_slugs: Dict[str, Set[str]] = {}
        if preset:
            for cat in ALL_TAG_CATEGORIES:
                preset_slugs[cat] = {t.slug for t in preset.groups.get(cat, []) if t.slug}

        for cat in ALL_TAG_CATEGORIES:
            merged: Dict[str, str] = {}
            checked: Set[str] = set()

            if preset and cat in CONSTRAINED_CATEGORIES:
                for tag in preset.groups.get(cat, []):
                    if tag.slug:
                        merged[tag.slug] = tag.name

            unknown_map: Dict[str, str] = {}

            for slug, conf in sorted(ai_conf_map[cat].items()):
                base = resolve_name(cat, slug)
                entry = f"{base} ({conf:.2f})"
                if preset and cat in CONSTRAINED_CATEGORIES and slug not in preset_slugs.get(cat, set()):
                    unknown_map[slug] = entry
                else:
                    merged[slug] = entry
                checked.add(slug)

            for slug in sorted(info_slugs.get(cat, set())):
                if slug not in merged:
                    merged[slug] = resolve_name(cat, slug)
                checked.add(slug)

            items = [
                (slug, merged[slug], slug in checked)
                for slug in sorted(merged)
            ]
            self._panels[cat].load_checkboxes(items)
            self._panels[cat].load_unknown(
                [(slug, unknown_map[slug]) for slug in sorted(unknown_map)]
            )

        if info:
            self._set_form(info)
        else:
            self._clear_form()

    def _set_form(self, info: GalleryInfo):
        self._title_input.setText(info.title)
        self._set_category(info.category)
        self._language_input.setText(info.language)
        self._original_file_count = dict(info.file_count)
        self._original_file_size = info.file_size
        self._image_count_label.setText(str(self._original_file_count.get("image", 0)))
        self._video_count_label.setText(str(self._original_file_count.get("video", 0)))
        self._file_size_label.setText(f"{self._original_file_size} bytes")

    def _set_category(self, cat: str):
        rb = self._category_radios.get(cat)
        if rb:
            rb.setChecked(True)

    def _get_category(self) -> str:
        checked = self._category_group.checkedButton()
        if checked is not None:
            for key, rb in self._category_radios.items():
                if rb is checked:
                    return key
        return ""

    def collect_info(self) -> GalleryInfo:
        info = GalleryInfo()
        info.title = self._title_input.text().strip()
        info.category = self._get_category()
        info.language = self._language_input.text().strip()
        info.file_count = dict(self._original_file_count)
        info.file_size = self._original_file_size
        for cat in ALL_TAG_CATEGORIES:
            info.tags[cat] = self._panels[cat].get_checked()
        return info

    def _clear_form(self):
        self._title_input.clear()
        self._category_group.setExclusive(False)
        for rb in self._category_radios.values():
            rb.setChecked(False)
        self._category_group.setExclusive(True)
        self._language_input.clear()
        self._original_file_count = {"image": 0, "video": 0}
        self._original_file_size = 0
        self._image_count_label.setText("0")
        self._video_count_label.setText("0")
        self._file_size_label.setText("0 bytes")
