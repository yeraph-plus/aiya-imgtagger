from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QComboBox, QToolBar, QDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer

from kernel.bus import DataBus
from kernel.agent import AIAgentClient, ModelListFetcher
from kernel.prompt_service import PresetService
from kernel.task_manager import TaskManager
from kernel.models import PresetTagSet, TaskState
from kernel.storage import Storage
from ui.task_tree import TaskTreeWidget
from ui.preview_panel import PreviewPanel


class BatchTaggerWindow(QMainWindow):
    def __init__(self, entry_path: str = None, preset_name: str = None):
        super().__init__()
        self.setWindowTitle("Aiya Batch Tagger")
        self.resize(1280, 800)

        self._bus = DataBus()
        self._current_model: str = ""
        self._available_models: list[str] = []
        self._api_checked: bool = False
        self._presets = PresetService.list_all()
        self._current_preset: Optional[PresetTagSet] = None

        self._task_manager: Optional[TaskManager] = None
        self._ai_processing: bool = False
        self._batch_errors: list[tuple[str, str]] = []

        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

        self._rebuild_preset_combo()

        if entry_path:
            self._apply_entry(Path(entry_path))
        if preset_name:
            preset = self._presets.get(preset_name)
            if preset:
                self._apply_preset(preset_name)

        QTimer.singleShot(100, self._on_refresh_models)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._on_open_folder)
        toolbar.addWidget(open_btn)

        self._refresh_btn = QPushButton("Refresh Models")
        self._refresh_btn.clicked.connect(self._on_refresh_models)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addSeparator()

        self._model_label = QLabel("Model:")
        toolbar.addWidget(self._model_label)

        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        self._model_combo.currentTextChanged.connect(self._on_model_selected)
        toolbar.addWidget(self._model_combo)

        toolbar.addSeparator()

        self._preset_label = QLabel("Template:")
        toolbar.addWidget(self._preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(120)
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)
        toolbar.addWidget(self._preset_combo)

        toolbar.addSeparator()

        self._preview_btn = QPushButton("Preview Prompt")
        self._preview_btn.clicked.connect(self._on_preview_prompt)
        toolbar.addWidget(self._preview_btn)

        toolbar.addSeparator()

        self._batch_btn = QPushButton("Batch AI")
        self._batch_btn.clicked.connect(self._on_batch_ai)
        toolbar.addWidget(self._batch_btn)

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
        tree_group_layout.addWidget(self._task_tree)
        self._splitter.addWidget(tree_group)

        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(6)

        preview_group = QGroupBox("Preview")
        preview_group_layout = QVBoxLayout(preview_group)
        preview_group_layout.setContentsMargins(4, 4, 4, 4)
        self._preview_panel = PreviewPanel()
        self._preview_panel.set_bus(self._bus)
        preview_group_layout.addWidget(self._preview_panel)
        right_panel_layout.addWidget(preview_group)

        self._splitter.addWidget(right_panel)
        self._splitter.setSizes([280, 980])

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_label = QLabel("Ready")
        self._statusbar.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._statusbar.addPermanentWidget(self._progress_bar)

    def _update_status(self, text: str):
        self._status_label.setText(text)

    def _on_refresh_models(self):
        self._refresh_btn.setEnabled(False)
        self._update_status("Fetching model list...")

        self._model_worker = ModelListFetcher()
        self._model_worker.finished.connect(self._on_models_loaded)
        self._model_worker.error.connect(self._on_models_error)
        self._model_worker.finished.connect(self._model_worker.deleteLater)
        self._model_worker.start()

    def _on_models_loaded(self, models: list):
        self._available_models = models
        self._api_checked = True
        self._rebuild_model_combo()
        self._update_status(f"Loaded {len(models)} models")
        self._refresh_btn.setEnabled(True)

    def _on_models_error(self, error: str):
        self._api_checked = False
        QMessageBox.critical(self, "API Error", f"Failed to fetch models:\n{error}")
        self._update_status("API check failed")
        self._refresh_btn.setEnabled(True)

    def _rebuild_model_combo(self):
        self._model_combo.blockSignals(True)
        self._model_combo.clear()

        select_index = -1
        for i, model_id in enumerate(self._available_models):
            self._model_combo.addItem(model_id)
            if model_id == self._current_model:
                select_index = i

        self._model_combo.blockSignals(False)

        if select_index >= 0:
            self._model_combo.setCurrentIndex(select_index)
        elif self._available_models:
            self._model_combo.setCurrentIndex(0)
            self._current_model = self._available_models[0]

        self._update_controls()

    def _on_model_selected(self, text: str):
        if text:
            self._current_model = text
            self._update_status(f"Model: {text}")

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
            self._update_status(f"Template: {text}")
        else:
            self._current_preset = None
            self._update_status("Template: None")

    def _on_preview_prompt(self):
        prompt = AIAgentClient.get_system_prompt(self._current_preset)
        dlg = QDialog(self)
        dlg.setWindowTitle("Prompt Preview")
        dlg.resize(800, 600)
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(prompt)
        layout.addWidget(text_edit)
        dlg.exec()

    def _on_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            path = Path(folder)
            AIAgentClient.clear_prompt_cache()
            self._bus.load_entry(path)
            self._preview_panel.clear()
            self._update_controls()
            self._update_status(f"Opened: {path} ({self._bus.get_task_count()} subfolders)")

    def _update_controls(self):
        has_folder = self._bus.entry_path is not None
        has_model = bool(self._current_model and self._api_checked)
        processing = self._ai_processing

        self._batch_btn.setEnabled(has_folder and has_model and not processing)

    def _apply_entry(self, path: Path):
        AIAgentClient.clear_prompt_cache()
        self._bus.load_entry(path)
        self._preview_panel.clear()
        self._update_controls()
        self._update_status(f"Opened: {path} ({self._bus.get_task_count()} subfolders)")

    def _apply_preset(self, preset_name: str):
        self._preset_combo.blockSignals(True)
        idx = self._preset_combo.findText(preset_name)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)
        self._current_preset = self._presets.get(preset_name)

    def _on_batch_ai(self):
        if self._bus.entry_path is None:
            return
        if not self._current_model or not self._api_checked:
            QMessageBox.warning(self, "No Model", "Please refresh model list first.")
            return

        tasks = self._bus.get_all_tasks()
        folders_to_process = [t for t in tasks if t.state not in (TaskState.COMPLETED,) and not Storage.has_tags(t.path)]

        if not folders_to_process:
            QMessageBox.information(self, "Batch AI", "No subfolders without ai_tags.json found.")
            return

        total = self._bus.get_task_count()
        pending_count = len(folders_to_process)

        reply = QMessageBox.question(
            self, "Batch AI",
            f"Process {pending_count} of {total} folder(s)?\nFolders with existing ai_tags.json will be skipped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._ai_processing = True
        self._update_controls()
        self._batch_btn.setText("Stop")
        self._safe_disconnect(self._batch_btn.clicked)
        self._batch_btn.clicked.connect(self._on_stop_batch)

        self._batch_errors = []

        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(0)

        self._task_manager = TaskManager(self._bus, self._current_model, self._current_preset)
        self._task_manager.progress.connect(self._on_batch_progress)
        self._task_manager.folder_completed.connect(self._on_batch_folder_done)
        self._task_manager.folder_error.connect(self._on_batch_folder_error)
        self._task_manager.finished.connect(self._on_batch_finished)
        self._task_manager.start()

    def _on_stop_batch(self):
        if self._task_manager:
            self._task_manager.cancel()
            self._update_status("Stopping...")

    def _on_batch_progress(self, current: int, total: int):
        self._progress_bar.setValue(current)
        self._update_status(f"Batch: {current}/{total}")

    def _on_batch_folder_done(self, name: str):
        self._update_status(f"Done: {name}")

    def _on_batch_folder_error(self, name: str, error: str):
        self._batch_errors.append((name, error))
        self._update_status(f"Error: {name}")

    def _on_batch_finished(self):
        self._ai_processing = False
        self._progress_bar.setVisible(False)
        self._batch_btn.setText("Batch AI")
        self._safe_disconnect(self._batch_btn.clicked)
        self._batch_btn.clicked.connect(self._on_batch_ai)
        self._bus.refresh()
        self._update_controls()
        errors = self._batch_errors
        self._batch_errors = []
        self._task_manager = None
        if errors:
            preview = "\n".join(f"- {n}: {e[:120]}" for n, e in errors[:8])
            tail = f"\n... and {len(errors) - 8} more." if len(errors) > 8 else ""
            QMessageBox.warning(
                self, "Batch Errors",
                f"{len(errors)} folder(s) failed:\n{preview}{tail}",
            )
        self._update_status("Batch complete")

    def closeEvent(self, event):
        if self._task_manager:
            self._task_manager.cancel()
        self._bus.shutdown()
        event.accept()

    @staticmethod
    def _safe_disconnect(signal):
        try:
            signal.disconnect()
        except (TypeError, RuntimeError):
            pass
