import uuid
from typing import Dict, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QTabWidget,
    QLineEdit, QComboBox, QInputDialog, QMessageBox, QStatusBar,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal

from config import CONSTRAINED_CATEGORIES
from kernel.models import PresetTagSet, PresetTag
from kernel.prompt_service import PresetService

_COL_SLUG = 0
_COL_NAME = 1
_COL_DESC = 2
_COL_ACTIONS = 3


class _TagGroupTable(QWidget):
    _on_change = pyqtSignal()

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self._category = category
        self._tags: List[PresetTag] = []
        self._editing_tag_id: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Slug", "Name", "Description", ""])
        self._table.horizontalHeader().setSectionResizeMode(_COL_SLUG, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(_COL_DESC, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(_COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_SLUG, 140)
        self._table.setColumnWidth(_COL_ACTIONS, 76)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setStyleSheet(
            "QTableWidget::item:selected { background-color: #cce5ff; color: #000000; }"
            "QTableWidget::item:focus { outline: none; }"
        )
        self._table.setAlternatingRowColors(True)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self._table)

        input_box = QVBoxLayout()
        input_box.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._slug_input = QLineEdit()
        self._slug_input.setPlaceholderText("slug")
        self._slug_input.setMinimumWidth(130)
        self._slug_input.returnPressed.connect(self._submit)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Name")
        self._name_input.returnPressed.connect(self._submit)

        self._submit_btn = QPushButton("Add")
        self._submit_btn.setMinimumWidth(70)
        self._submit_btn.clicked.connect(self._submit)

        row1.addWidget(self._slug_input)
        row1.addWidget(self._name_input)
        row1.addWidget(self._submit_btn)
        row1.addStretch()

        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Description")
        self._desc_input.returnPressed.connect(self._submit)

        row2.addWidget(self._desc_input)

        input_box.addLayout(row1)
        input_box.addLayout(row2)
        layout.addLayout(input_box)

    def load_tags(self, tags: List[PresetTag]):
        self._tags = list(tags)
        self._cancel_edit()
        self._rebuild_table()

    def get_tags(self) -> List[PresetTag]:
        return list(self._tags)

    def _rebuild_table(self):
        self._table.setRowCount(0)

        for tag in self._tags:
            row = self._table.rowCount()
            self._table.insertRow(row)

            slug_item = QTableWidgetItem(tag.slug)
            slug_item.setData(Qt.ItemDataRole.UserRole, tag.id)
            slug_item.setFlags(slug_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_SLUG, slug_item)

            name_item = QTableWidgetItem(tag.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_NAME, name_item)

            desc_item = QTableWidgetItem(tag.description)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_DESC, desc_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 1, 2, 1)
            actions_layout.setSpacing(2)

            edit_btn = QPushButton("Ed")
            edit_btn.setFixedSize(28, 22)
            edit_btn.setToolTip("Edit this tag")
            edit_btn.clicked.connect(lambda checked, tag_id=tag.id: self._start_edit(tag_id))

            del_btn = QPushButton("\u00d7")
            del_btn.setFixedSize(22, 22)
            del_btn.setToolTip("Delete tag")
            del_btn.clicked.connect(lambda checked, tag_id=tag.id: self._delete_by_id(tag_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(del_btn)
            self._table.setCellWidget(row, _COL_ACTIONS, actions_widget)

    def _start_edit(self, tag_id: str):
        for tag in self._tags:
            if tag.id == tag_id:
                self._editing_tag_id = tag_id
                self._slug_input.setText(tag.slug)
                self._name_input.setText(tag.name)
                self._desc_input.setText(tag.description)
                self._submit_btn.setText("Update")
                self._slug_input.setFocus()
                return

    def _cancel_edit(self):
        self._editing_tag_id = ""
        self._slug_input.clear()
        self._name_input.clear()
        self._desc_input.clear()
        self._submit_btn.setText("Add")

    def _submit(self):
        slug = self._slug_input.text().strip().lower().replace(" ", "_")
        if not slug:
            return

        if self._editing_tag_id:
            for tag in self._tags:
                if tag.id == self._editing_tag_id:
                    tag.slug = slug
                    tag.name = self._name_input.text().strip()
                    tag.description = self._desc_input.text().strip()
                    break
        else:
            for tag in self._tags:
                if tag.slug == slug:
                    QMessageBox.warning(self, "Duplicate Slug", f"Slug '{slug}' already exists in this group.")
                    return
            tag = PresetTag(
                id=uuid.uuid4().hex,
                slug=slug,
                name=self._name_input.text().strip(),
                description=self._desc_input.text().strip(),
            )
            self._tags.append(tag)

        self._cancel_edit()
        self._rebuild_table()
        self._table.scrollToBottom()
        self._slug_input.setFocus()
        self._on_change.emit()

    def _delete_by_id(self, tag_id: str):
        if self._editing_tag_id == tag_id:
            self._cancel_edit()
        self._tags = [t for t in self._tags if t.id != tag_id]
        self._rebuild_table()
        self._on_change.emit()


class PresetEditorWindow(QMainWindow):
    def __init__(self, preset_name: str = None):
        super().__init__()
        self.setWindowTitle("Preset Tag Editor")
        self.resize(1000, 700)

        self._presets: Dict[str, PresetTagSet] = {}
        self._current_type: str = ""

        self._setup_ui()
        self._load_presets()

        if preset_name and preset_name in self._presets:
            self._auto_select_preset(preset_name)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        toolbar.addWidget(QLabel("Preset:"))

        self._type_combo = QComboBox()
        self._type_combo.setMinimumWidth(120)
        self._type_combo.currentTextChanged.connect(self._on_type_selected)
        toolbar.addWidget(self._type_combo)

        self._new_btn = QPushButton("New Preset")
        self._new_btn.clicked.connect(self._add_type)
        self._delete_btn = QPushButton("Delete Preset")
        self._delete_btn.clicked.connect(self._delete_type)
        toolbar.addWidget(self._new_btn)
        toolbar.addWidget(self._delete_btn)

        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        self._tab_widget = QTabWidget()
        self._group_tables: Dict[str, _TagGroupTable] = {}

        for cat in CONSTRAINED_CATEGORIES:
            table_widget = _TagGroupTable(cat)
            table_widget._on_change.connect(self._instant_save)
            self._group_tables[cat] = table_widget
            self._tab_widget.addTab(table_widget, cat.capitalize())

        main_layout.addWidget(self._tab_widget)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    def _load_presets(self):
        self._presets = PresetService.list_all()
        self._rebuild_type_combo()
        self._statusbar.showMessage("Loaded")

    def _auto_select_preset(self, preset_name: str):
        idx = self._type_combo.findText(preset_name)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
            self._statusbar.showMessage(f"Loaded '{preset_name}'")

    def _rebuild_type_combo(self):
        self._type_combo.blockSignals(True)
        self._type_combo.clear()

        preset_types = PresetService.get_preset_types(self._presets)
        for pt in preset_types:
            self._type_combo.addItem(pt)

        if preset_types:
            self._type_combo.setCurrentIndex(0)
            self._on_type_selected(preset_types[0])
        else:
            self._current_type = ""
            for cat in CONSTRAINED_CATEGORIES:
                self._group_tables[cat].load_tags([])

        self._type_combo.blockSignals(False)

    def _on_type_selected(self, text: str):
        self._current_type = text

        ps = self._presets.get(text)
        if ps:
            for cat in CONSTRAINED_CATEGORIES:
                tags = ps.groups.get(cat, [])
                self._group_tables[cat].load_tags(tags)
        else:
            for cat in CONSTRAINED_CATEGORIES:
                self._group_tables[cat].load_tags([])

    def _instant_save(self):
        if not self._current_type or self._current_type not in self._presets:
            return
        ps = self._presets[self._current_type]
        for cat in CONSTRAINED_CATEGORIES:
            ps.groups[cat] = self._group_tables[cat].get_tags()
        PresetService.save(ps)
        self._statusbar.showMessage("Saved")

    def _add_type(self):
        text, ok = QInputDialog.getText(self, "New Preset", "Enter preset name:")
        if not ok or not text.strip():
            return
        text = text.strip()
        if text in self._presets:
            QMessageBox.warning(self, "Duplicate", f"Preset '{text}' already exists.")
            return

        self._presets[text] = PresetService.create(text)
        PresetService.save(self._presets[text])
        self._type_combo.blockSignals(True)
        self._type_combo.addItem(text)
        self._type_combo.setCurrentIndex(self._type_combo.count() - 1)
        self._type_combo.blockSignals(False)
        self._statusbar.showMessage(f"Created '{text}'")

    def _delete_type(self):
        text = self._type_combo.currentText()
        if not text or text not in self._presets:
            return

        reply = QMessageBox.question(
            self, "Delete",
            f"Delete preset '{text}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        PresetService.delete(text)
        self._presets.pop(text, None)

        self._type_combo.blockSignals(True)
        idx = self._type_combo.currentIndex()
        self._type_combo.removeItem(idx)
        if self._type_combo.count() > 0:
            self._type_combo.setCurrentIndex(0)
            self._current_type = self._type_combo.currentText()
        else:
            self._current_type = ""
            for cat in CONSTRAINED_CATEGORIES:
                self._group_tables[cat].load_tags([])
        self._type_combo.blockSignals(False)
        self._statusbar.showMessage(f"Deleted '{text}'")

    def closeEvent(self, event):
        event.accept()
