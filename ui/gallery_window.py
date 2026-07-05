import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QFileDialog, QMessageBox,
    QScrollArea, QGroupBox, QComboBox, QToolBar,
)
from PyQt6.QtCore import Qt

from kernel.info_service import InfoService
from kernel.prompt_service import PresetService
from kernel.models import PresetTagSet
from ui.gallery_tag_editor import GalleryTagEditor
from ui.preview_panel import ImageGridView
from ui.task_tree import TaskTreeWidget
from kernel.bus import DataBus


class GalleryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gallery Manager")
        self.resize(1280, 800)

        self._bus = DataBus()
        self._current_pid: Optional[str] = None
        self._presets = PresetService.list_all()
        self._current_preset: Optional[PresetTagSet] = None

        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

        self._rebuild_preset_combo()

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._on_open_folder)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(120)
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)
        toolbar.addWidget(self._preset_combo)

        toolbar.addSeparator()

        batch_btn = QPushButton("Batch Tagger")
        batch_btn.clicked.connect(lambda: self._launch("batch"))
        toolbar.addWidget(batch_btn)

        editor_btn = QPushButton("Tag Editor")
        editor_btn.clicked.connect(lambda: self._launch("editor"))
        toolbar.addWidget(editor_btn)

        spacer = QWidget()
        spacer.setSizePolicy(
            QWidget().sizePolicy().Policy.Expanding,
            QWidget().sizePolicy().Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(self._save_btn)

        self._save_next_btn = QPushButton("Save && Next")
        self._save_next_btn.clicked.connect(self._on_save_and_next)
        toolbar.addWidget(self._save_next_btn)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self._splitter)

        tree_group = QGroupBox("Folders")
        tree_group_layout = QVBoxLayout(tree_group)
        tree_group_layout.setContentsMargins(4, 4, 4, 4)
        self._task_tree = TaskTreeWidget()
        self._task_tree.set_bus(self._bus)
        self._task_tree.task_selected.connect(self._on_folder_selected)
        tree_group_layout.addWidget(self._task_tree)
        self._splitter.addWidget(tree_group)

        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(6)

        preview_group = QGroupBox("Preview")
        preview_group_layout = QVBoxLayout(preview_group)
        preview_group_layout.setContentsMargins(4, 4, 4, 4)
        self._image_preview = ImageGridView()
        preview_group_layout.addWidget(self._image_preview)
        right_panel_layout.addWidget(preview_group)

        editor_group = QGroupBox("Edit")
        editor_group_layout = QVBoxLayout(editor_group)
        editor_group_layout.setContentsMargins(4, 4, 4, 4)

        self._editor_scroll = QScrollArea()
        self._editor_scroll.setWidgetResizable(True)
        self._tag_editor = GalleryTagEditor()
        self._tag_editor.modified.connect(self._on_editor_modified)
        self._editor_scroll.setWidget(self._tag_editor)
        editor_group_layout.addWidget(self._editor_scroll)
        right_panel_layout.addWidget(editor_group, stretch=1)

        self._splitter.addWidget(right_panel)
        self._splitter.setSizes([280, 980])

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("Ready")
        self._statusbar.addWidget(self._status_label)

    def _rebuild_preset_combo(self):
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("None", None)
        presets = PresetService.get_preset_types(self._presets)
        for preset_type in presets:
            self._preset_combo.addItem(preset_type, preset_type)
        if presets:
            self._preset_combo.setCurrentIndex(1)
            self._current_preset = self._presets.get(presets[0])
        else:
            self._preset_combo.setCurrentIndex(0)
            self._current_preset = None
        self._preset_combo.blockSignals(False)

    def _on_preset_selected(self, text: str):
        if text and text != "None":
            self._current_preset = self._presets.get(text)
        else:
            self._current_preset = None
        self._reload_tag_editor()

    def _on_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._current_pid = None
            self._bus.load_entry(Path(folder))
            self._image_preview.clear()
            self._tag_editor.load_project(None, None, None)
            self._update_status(f"Opened: {folder}")

    def _on_folder_selected(self, pid: str):
        self._current_pid = pid
        task = self._bus.get_task(pid)
        if task:
            self._image_preview.load_from_bus(self._bus, pid)
        else:
            self._image_preview.clear()

        self._tag_editor.load_project(
            task.tag_data if task else None,
            task.info if task else None,
            self._current_preset,
        )
        self._update_status(task.name if task else "")

    def _reload_tag_editor(self):
        if self._current_pid:
            task = self._bus.get_task(self._current_pid)
            self._tag_editor.load_project(
                task.tag_data if task else None,
                task.info if task else None,
                self._current_preset,
            )

    def _on_save(self):
        if not self._current_pid:
            QMessageBox.warning(self, "Save", "No folder selected.")
            return
        info = self._tag_editor.collect_info()
        InfoService.save(Path(self._current_pid), info)
        self._update_status("Saved")

    def _on_save_and_next(self):
        if not self._current_pid:
            QMessageBox.warning(self, "Save & Next", "No folder selected.")
            return

        info = self._tag_editor.collect_info()
        InfoService.save(Path(self._current_pid), info)

        tasks = self._bus.get_all_tasks()
        keys = [t.id for t in tasks]
        try:
            idx = keys.index(self._current_pid)
            if idx + 1 < len(keys):
                next_id = keys[idx + 1]
                count = self._task_tree.topLevelItemCount()
                for i in range(count):
                    item = self._task_tree.topLevelItem(i)
                    data = item.data(0, Qt.ItemDataRole.UserRole)
                    if data == next_id:
                        self._task_tree.setCurrentItem(item)
                        self._task_tree.scrollToItem(item)
                        self._on_folder_selected(next_id)
                        return
        except ValueError:
            pass

        self._update_status("Saved")

    def _on_editor_modified(self):
        self._update_status("Modified")

    def _update_status(self, text: str):
        self._status_label.setText(text)

    def closeEvent(self, event):
        self._bus.shutdown()
        event.accept()

    def _launch(self, mode: str):
        root = Path(__file__).resolve().parent.parent
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--mode", mode]
        else:
            cmd = [sys.executable, str(root / "main.py"), "--mode", mode]

        if self._bus.entry_path:
            cmd += ["--entry", str(self._bus.entry_path)]
        if self._current_preset:
            cmd += ["--preset", self._current_preset.type]

        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
