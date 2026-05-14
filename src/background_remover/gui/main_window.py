"""Main desktop window scaffold."""

from __future__ import annotations

from pathlib import Path
import time

from background_remover.background import SUPPORTED_MODELS
from background_remover.gui.input_loader import (
    LoadedInput,
    PreviewFrame,
    is_supported_input_path,
    load_input,
    split_supported_paths,
)
from background_remover.gui.command_preview import build_command_preview
from background_remover.gui.model_metadata import describe_model
from background_remover.gui.output_paths import suggest_output_path
from background_remover.gui.processing_options import (
    GuiProcessingOptions,
    build_color_key_options,
    checked_path,
)
from background_remover.gui.settings import GuiSettings
from background_remover.gui.theme import MOCHA
from background_remover.gui.worker import ProcessingWorker
from background_remover.mask_cleanup import MaskCleanupOptions

from PySide6.QtCore import QThread, QSize, Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QSlider,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.qsettings = QSettings()
        self.gui_settings = GuiSettings.load(self.qsettings)
        self.loaded_input: LoadedInput | None = None
        self.processing_thread: QThread | None = None
        self.processing_worker: ProcessingWorker | None = None
        self.processing_started_at = 0.0
        self.completed_frame_seconds: list[float] = []
        self.last_successful_output_path: Path | None = None

        self.setWindowTitle("Aseprite Background Remover")
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        self._create_actions()
        self._create_toolbar()
        self._create_workspace()
        self._create_status_bar()
        self._restore_settings()
        self.open_action.triggered.connect(self.open_input_file)
        self.validate_action.triggered.connect(self.validate_settings)
        self.process_action.triggered.connect(self.start_processing)
        self.cancel_action.triggered.connect(self.cancel_processing)
        self.save_as_action.triggered.connect(self.choose_output_path)
        self.model_select.currentTextChanged.connect(self._update_model_metadata)
        self.cache_dir_input.textChanged.connect(self._update_model_metadata)
        self.preset_select.currentTextChanged.connect(self._apply_preset)
        self._update_model_metadata()
        self._update_command_preview()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_settings()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        style = self.style()
        self.open_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "Open",
            self,
        )
        self.process_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            "Process",
            self,
        )
        self.validate_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            "Validate",
            self,
        )
        self.cancel_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
            "Cancel",
            self,
        )
        self.save_as_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            "Save As",
            self,
        )
        self.about_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
            "About",
            self,
        )
        self.cancel_action.setEnabled(False)
        self.save_as_action.setEnabled(False)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.validate_action)
        toolbar.addAction(self.process_action)
        toolbar.addAction(self.cancel_action)
        toolbar.addSeparator()
        toolbar.addAction(self.save_as_action)
        toolbar.addSeparator()
        toolbar.addAction(self.about_action)
        self.addToolBar(toolbar)

    def _create_workspace(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._create_preview_area())
        main_splitter.addWidget(self._create_settings_panel())
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([860, 320])

        layout.addWidget(main_splitter, stretch=1)
        layout.addWidget(self._create_bottom_panel())
        self.setCentralWidget(root)

    def _create_preview_area(self) -> QWidget:
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        input_title = QLabel("Input")
        output_title = QLabel("Output")
        input_title.setObjectName("previewTitle")
        output_title.setObjectName("previewTitle")

        self.input_preview = PreviewPane("Drop or open an input file")
        self.output_preview = PreviewPane("Output appears after processing")
        self.input_preview.files_dropped.connect(self.load_dropped_files)
        self.output_preview.setEnabled(False)

        layout.addWidget(input_title, 0, 0)
        layout.addWidget(output_title, 0, 1)
        layout.addWidget(self.input_preview, 1, 0)
        layout.addWidget(self.output_preview, 1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 1)
        return container

    def _create_settings_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        panel = QWidget()
        scroll.setWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        model_group = QGroupBox("Model")
        model_layout = QVBoxLayout(model_group)
        self.preset_select = QComboBox()
        self.preset_select.addItems(
            [
                "Balanced Sprite",
                "Stylized Character",
                "Fast Draft",
                "Near-Solid Background",
                "Raw Model Output",
            ]
        )
        model_layout.addWidget(self.preset_select)
        self.model_select = QComboBox()
        self.model_select.addItems(SUPPORTED_MODELS)
        model_layout.addWidget(self.model_select)
        self.model_metadata_label = QLabel()
        self.model_metadata_label.setWordWrap(True)
        model_layout.addWidget(self.model_metadata_label)

        cache_row = QHBoxLayout()
        self.cache_dir_input = QLineEdit()
        self.cache_dir_input.setPlaceholderText(".cache/rembg-models")
        cache_button = QPushButton("Browse")
        cache_button.clicked.connect(lambda: self._choose_directory(self.cache_dir_input))
        cache_row.addWidget(self.cache_dir_input, stretch=1)
        cache_row.addWidget(cache_button)
        model_layout.addLayout(cache_row)

        logging_group = QGroupBox("Logging")
        logging_layout = QVBoxLayout(logging_group)
        self.logging_select = QComboBox()
        self.logging_select.addItems(["Normal", "Quiet", "Verbose", "Debug"])
        logging_layout.addWidget(self.logging_select)

        cleanup_group = QGroupBox("Cleanup")
        cleanup_layout = QFormLayout(cleanup_group)
        self.cleanup_enabled = QCheckBox("Enabled")
        self.cleanup_enabled.setChecked(True)
        self.alpha_threshold_enabled = QCheckBox("Alpha threshold")
        self.alpha_threshold = QSpinBox()
        self.alpha_threshold.setRange(0, 255)
        self.alpha_threshold.setValue(8)
        self.alpha_threshold.setEnabled(False)
        self.alpha_threshold_enabled.toggled.connect(self.alpha_threshold.setEnabled)
        self.min_artifact_size = QSpinBox()
        self.min_artifact_size.setRange(0, 1_000_000)
        self.min_artifact_size.setValue(4)
        self.fill_hole_size = QSpinBox()
        self.fill_hole_size.setRange(0, 1_000_000)
        self.fill_hole_size.setValue(0)
        self.keep_largest_component = QCheckBox("Keep largest component")
        self.feather_radius = QDoubleSpinBox()
        self.feather_radius.setRange(0.0, 128.0)
        self.feather_radius.setDecimals(2)
        self.feather_radius.setSingleStep(0.25)
        self.feather_radius.setValue(0.0)
        cleanup_layout.addRow(self.cleanup_enabled)
        cleanup_layout.addRow(self.alpha_threshold_enabled, self.alpha_threshold)
        cleanup_layout.addRow("Min artifact size", self.min_artifact_size)
        cleanup_layout.addRow("Fill hole size", self.fill_hole_size)
        cleanup_layout.addRow(self.keep_largest_component)
        cleanup_layout.addRow("Feather radius", self.feather_radius)

        color_group = QGroupBox("Color Key")
        color_layout = QFormLayout(color_group)
        self.color_key_sample_corners = QCheckBox("Sample corners")
        self.color_key_color = QLineEdit()
        self.color_key_color.setPlaceholderText("#ffffff or 255,255,255")
        color_pick = QPushButton("Pick")
        color_pick.clicked.connect(self._choose_color_key_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_key_color, stretch=1)
        color_row.addWidget(color_pick)
        self.color_key_tolerance = QDoubleSpinBox()
        self.color_key_tolerance.setRange(0.0, 512.0)
        self.color_key_tolerance.setDecimals(1)
        self.color_key_tolerance.setValue(24.0)
        self.color_key_protect_alpha = QSpinBox()
        self.color_key_protect_alpha.setRange(0, 255)
        self.color_key_protect_alpha.setValue(224)
        color_layout.addRow(self.color_key_sample_corners)
        color_layout.addRow("Color", color_row)
        color_layout.addRow("Tolerance", self.color_key_tolerance)
        color_layout.addRow("Protect alpha", self.color_key_protect_alpha)

        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Choose Save As before final export")
        self.overwrite_output = QCheckBox("Replace existing output")
        output_layout.addWidget(self.output_path_input)
        output_layout.addWidget(self.overwrite_output)

        artifacts_group = QGroupBox("Artifacts")
        artifacts_layout = QFormLayout(artifacts_group)
        self.frame_output_enabled, self.frame_output_dir = self._artifact_row(
            artifacts_layout,
            "Processed frames",
            directory=True,
        )
        self.mask_output_enabled, self.mask_output_dir = self._artifact_row(
            artifacts_layout,
            "Final masks",
            directory=True,
        )
        self.ai_mask_output_enabled, self.ai_mask_output_dir = self._artifact_row(
            artifacts_layout,
            "AI masks",
            directory=True,
        )
        self.color_key_mask_output_enabled, self.color_key_mask_output_dir = self._artifact_row(
            artifacts_layout,
            "Color-key masks",
            directory=True,
        )
        self.still_mask_output_enabled, self.still_mask_output_path = self._artifact_row(
            artifacts_layout,
            "Still mask",
            directory=False,
            file_filter="PNG images (*.png)",
        )
        self.report_output_enabled, self.report_output_path = self._artifact_row(
            artifacts_layout,
            "JSON report",
            directory=False,
            file_filter="JSON reports (*.json)",
        )
        self.contact_sheet_output_enabled, self.contact_sheet_output_path = self._artifact_row(
            artifacts_layout,
            "Contact sheet",
            directory=False,
            file_filter="PNG images (*.png)",
        )
        self.preview_output_enabled, self.preview_output_path = self._artifact_row(
            artifacts_layout,
            "GIF preview",
            directory=False,
            file_filter="GIF images (*.gif)",
        )

        report_group = QGroupBox("Report Warnings")
        report_layout = QFormLayout(report_group)
        self.area_jump_threshold = QDoubleSpinBox()
        self.area_jump_threshold.setRange(0.0, 100.0)
        self.area_jump_threshold.setDecimals(3)
        self.area_jump_threshold.setSingleStep(0.05)
        self.area_jump_threshold.setValue(0.25)
        self.bbox_jump_threshold = QDoubleSpinBox()
        self.bbox_jump_threshold.setRange(0.0, 100_000.0)
        self.bbox_jump_threshold.setDecimals(1)
        self.bbox_jump_threshold.setValue(32.0)
        report_layout.addRow("Area jump ratio", self.area_jump_threshold)
        report_layout.addRow("BBox jump px", self.bbox_jump_threshold)

        command_group = QGroupBox("Command Preview")
        command_layout = QVBoxLayout(command_group)
        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(92)
        command_layout.addWidget(self.command_preview)

        metadata_group = QGroupBox("Input Metadata")
        metadata_layout = QVBoxLayout(metadata_group)
        self.input_metadata_label = QLabel("No input loaded")
        self.input_metadata_label.setWordWrap(True)
        metadata_layout.addWidget(self.input_metadata_label)

        layout.addWidget(model_group)
        layout.addWidget(logging_group)
        layout.addWidget(cleanup_group)
        layout.addWidget(color_group)
        layout.addWidget(output_group)
        layout.addWidget(artifacts_group)
        layout.addWidget(report_group)
        layout.addWidget(command_group)
        layout.addWidget(metadata_group)
        layout.addStretch(1)
        self._connect_command_preview_controls(panel)
        return scroll

    def _create_bottom_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        top_row.addWidget(self.status_label)
        top_row.addWidget(self.progress_bar, stretch=1)

        self.warnings_panel = QPlainTextEdit()
        self.warnings_panel.setReadOnly(True)
        self.warnings_panel.setPlaceholderText("Warnings and generated artifacts")
        self.warnings_panel.setMaximumHeight(88)

        layout.addLayout(top_row)
        layout.addWidget(self.warnings_panel)
        return panel

    def _create_status_bar(self) -> None:
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

    def _restore_settings(self) -> None:
        model_index = self.model_select.findText(self.gui_settings.model_name)
        if model_index >= 0:
            self.model_select.setCurrentIndex(model_index)
        self.cache_dir_input.setText(str(self.gui_settings.model_cache_dir))

    def _persist_settings(self) -> None:
        current = GuiSettings(
            recent_folders=self.gui_settings.recent_folders,
            model_name=self.model_select.currentText(),
            model_cache_dir=Path(self.cache_dir_input.text() or ".cache/rembg-models"),
        )
        current.save(self.qsettings)

    def _artifact_row(
        self,
        layout: QFormLayout,
        label: str,
        *,
        directory: bool,
        file_filter: str = "All files (*)",
    ) -> tuple[QCheckBox, QLineEdit]:
        enabled = QCheckBox()
        path_input = QLineEdit()
        browse = QPushButton("Browse")
        browse.clicked.connect(
            lambda: self._choose_directory(path_input)
            if directory
            else self._choose_file(path_input, file_filter)
        )
        row = QHBoxLayout()
        row.addWidget(enabled)
        row.addWidget(path_input, stretch=1)
        row.addWidget(browse)
        layout.addRow(label, row)
        return enabled, path_input

    def _choose_directory(self, target: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose Folder", target.text())
        if directory:
            target.setText(directory)

    def _choose_file(self, target: QLineEdit, file_filter: str) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Choose Output",
            target.text(),
            file_filter,
        )
        if path:
            target.setText(path)

    def _choose_color_key_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.color_key_color.setText(color.name())

    def _connect_command_preview_controls(self, panel: QWidget) -> None:
        for line_edit in panel.findChildren(QLineEdit):
            line_edit.textChanged.connect(self._update_command_preview)
        for combo_box in panel.findChildren(QComboBox):
            combo_box.currentTextChanged.connect(self._update_command_preview)
        for checkbox in panel.findChildren(QCheckBox):
            checkbox.toggled.connect(self._update_command_preview)
        for spinbox in panel.findChildren(QSpinBox):
            spinbox.valueChanged.connect(self._update_command_preview)
        for spinbox in panel.findChildren(QDoubleSpinBox):
            spinbox.valueChanged.connect(self._update_command_preview)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if _event_has_files(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = _paths_from_drop(event)
        if paths:
            self.load_dropped_files(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def open_input_file(self) -> None:
        start_dir = str(self.gui_settings.recent_folders[0]) if self.gui_settings.recent_folders else ""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Input",
            start_dir,
            "Supported inputs (*.aseprite *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )
        if path:
            self.load_input_path(Path(path), skipped=[])

    def choose_output_path(self) -> None:
        if self.loaded_input is None:
            self._show_error("Load an input before choosing an output path.")
            return
        suggested = self.output_path_input.text() or str(
            suggest_output_path(self.loaded_input.metadata.path)
        )
        if self.loaded_input.metadata.input_type == "aseprite":
            filter_text = "Aseprite files (*.aseprite)"
        else:
            filter_text = "PNG images (*.png)"
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Output As",
            suggested,
            filter_text,
        )
        if path:
            self.output_path_input.setText(path)

    def load_dropped_files(self, paths: list[Path]) -> None:
        selected, skipped = split_supported_paths(paths)
        if selected is None:
            self._show_error("Unsupported drop. Use .aseprite or a supported still image.")
            return
        self.load_input_path(selected, skipped=skipped)

    def load_input_path(self, path: Path, *, skipped: list[Path] | None = None) -> None:
        if not is_supported_input_path(path):
            self._show_error(f"Unsupported input extension: {path.suffix or path.name}")
            return

        self.status_label.setText("Loading input")
        self.statusBar().showMessage(f"Loading {path}")
        self.progress_bar.setRange(0, 0)
        self.input_preview.set_message("Loading input")

        try:
            loaded = load_input(path)
        except Exception as error:  # GUI boundary: convert parser/Pillow errors into UI text.
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self._show_error(str(error))
            return

        self._apply_loaded_input(loaded, skipped or [])

    def _apply_loaded_input(self, loaded: LoadedInput, skipped: list[Path]) -> None:
        self.loaded_input = loaded
        metadata = loaded.metadata
        self.input_preview.set_frames(loaded.frames)
        self.input_metadata_label.setText(_format_metadata(loaded))
        self.output_path_input.setText(str(suggest_output_path(metadata.path)))
        self._fill_suggested_artifact_paths(metadata.path)
        self.process_action.setEnabled(True)
        self.save_as_action.setEnabled(True)
        self.gui_settings.recent_folders = _updated_recent_folders(
            self.gui_settings.recent_folders,
            metadata.path.parent,
        )
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.statusBar().showMessage(f"Loaded {metadata.path}")

        warnings = list(metadata.warnings)
        if skipped:
            skipped_names = ", ".join(path.name for path in skipped)
            warnings.append(f"Skipped dropped files: {skipped_names}")
        self.warnings_panel.setPlainText("\n".join(warnings))
        self._update_command_preview()

    def _show_error(self, message: str) -> None:
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.warnings_panel.setPlainText(message)
        self.input_preview.set_message(message)

    def validate_settings(self) -> None:
        try:
            _output_path, options = self._collect_processing_request()
        except ValueError as error:
            self._show_validation_error(str(error))
            return
        command = self._command_preview_for(options)
        self.warnings_panel.setPlainText(f"Settings valid.\n{command}")
        self.status_label.setText("Valid")
        self.statusBar().showMessage("Settings are valid")

    def start_processing(self) -> None:
        if self.loaded_input is None:
            self._show_error("Load an input before processing.")
            return
        try:
            output_path, options = self._collect_processing_request()
        except ValueError as error:
            self._show_validation_error(str(error))
            return

        overwrite = self.overwrite_output.isChecked()
        if output_path.exists() and not overwrite:
            answer = QMessageBox.question(
                self,
                "Replace Existing Output",
                f"{output_path} already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        self._set_processing_state(True)
        self.processing_started_at = time.perf_counter()
        self.completed_frame_seconds = []
        self.status_label.setText("Preparing")
        self.statusBar().showMessage("Starting background removal")
        self.progress_bar.setRange(0, 0)

        worker = ProcessingWorker(
            loaded_input=self.loaded_input,
            output_path=output_path,
            model_name=self.model_select.currentText(),
            options=options,
            overwrite=overwrite,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._handle_progress)
        worker.completed.connect(self._handle_processing_completed)
        worker.failed.connect(self._handle_processing_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_refs)
        self.processing_worker = worker
        self.processing_thread = thread
        thread.start()

    def cancel_processing(self) -> None:
        if self.processing_worker is not None:
            self.processing_worker.cancel()
            self.status_label.setText("Cancelling")
            self.statusBar().showMessage("Cancelling after the current frame")
            self.cancel_action.setEnabled(False)

    def _handle_progress(self, event) -> None:
        elapsed = time.perf_counter() - self.processing_started_at
        if event.stage in {"loading", "model"}:
            self.progress_bar.setRange(0, 0)
            self.status_label.setText(event.message or event.stage.title())
            self.statusBar().showMessage(event.message or event.stage.title())
            return
        if event.stage == "processing" and event.frame_count:
            self.progress_bar.setRange(0, event.frame_count)
            self.progress_bar.setValue(event.frame_index or 0)
            frame_number = (event.frame_index or 0) + 1
            self.status_label.setText(f"Processing frame {frame_number}/{event.frame_count}")
            self.statusBar().showMessage(f"Elapsed {elapsed:.1f}s")
            return
        if event.stage == "frame_completed" and event.frame_count:
            self.completed_frame_seconds.append(event.elapsed_seconds)
            average = sum(self.completed_frame_seconds) / len(self.completed_frame_seconds)
            self.progress_bar.setRange(0, event.frame_count)
            self.progress_bar.setValue(event.frame_index or 0)
            self.status_label.setText(f"Processed frame {event.frame_index}/{event.frame_count}")
            self.statusBar().showMessage(f"Elapsed {elapsed:.1f}s, average frame {average:.2f}s")
            return
        if event.stage == "completed":
            self.progress_bar.setRange(0, event.frame_count or 1)
            self.progress_bar.setValue(event.frame_count or 1)

    def _handle_processing_completed(self, result) -> None:
        output_path = result.artifacts.output_path
        self.last_successful_output_path = output_path
        self._set_processing_state(False)
        self.status_label.setText("Complete")
        self.statusBar().showMessage(f"Wrote {output_path}")
        warnings = []
        if hasattr(result, "warnings"):
            warnings.extend(warning["message"] for warning in result.warnings)
        warnings.append(f"Wrote {output_path}")
        warnings.append(f"Processing time: {result.timings.processing_seconds:.2f}s")
        if result.timings.average_frame_seconds:
            warnings.append(f"Average frame time: {result.timings.average_frame_seconds:.2f}s")
        self.warnings_panel.setPlainText("\n".join(warnings))
        self._load_output_preview(output_path)

    def _handle_processing_failed(self, message: str) -> None:
        self._set_processing_state(False)
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.warnings_panel.setPlainText(message)

    def _load_output_preview(self, output_path: Path) -> None:
        try:
            loaded = load_input(output_path)
        except Exception as error:
            self.warnings_panel.appendPlainText(f"Could not load output preview: {error}")
            return
        self.output_preview.setEnabled(True)
        self.output_preview.set_frames(loaded.frames)
        self._sync_output_to_input()

    def _sync_output_to_input(self) -> None:
        if len(self.input_preview.frames) <= 1 or len(self.output_preview.frames) <= 1:
            return
        if len(self.input_preview.frames) != len(self.output_preview.frames):
            return
        try:
            self.input_preview.frame_changed.connect(
                self._sync_output_frame,
                Qt.ConnectionType.UniqueConnection,
            )
        except TypeError:
            pass
        self.output_preview.set_frame_index(self.input_preview.current_frame_index)

    def _sync_output_frame(self, index: int) -> None:
        if len(self.input_preview.frames) == len(self.output_preview.frames):
            self.output_preview.set_frame_index(index)

    def _collect_processing_request(self) -> tuple[Path, GuiProcessingOptions]:
        if self.loaded_input is None:
            raise ValueError("Load an input before processing.")
        output_text = self.output_path_input.text().strip()
        output_path = Path(output_text) if output_text else suggest_output_path(self.loaded_input.metadata.path)
        if not output_text:
            self.output_path_input.setText(str(output_path))

        logging_mode = self.logging_select.currentText()
        verbose = 1 if logging_mode == "Verbose" else 2 if logging_mode == "Debug" else 0
        color_key_options = build_color_key_options(
            sample_corners=self.color_key_sample_corners.isChecked(),
            color_text=self.color_key_color.text(),
            tolerance=self.color_key_tolerance.value(),
            protect_alpha=self.color_key_protect_alpha.value(),
        )
        options = GuiProcessingOptions(
            model_cache_dir=Path(self.cache_dir_input.text() or ".cache/rembg-models"),
            quiet=logging_mode == "Quiet",
            verbose=verbose,
            cleanup_options=self._cleanup_options_from_ui(),
            color_key_options=color_key_options,
            frame_output_dir=checked_path(
                self.frame_output_enabled.isChecked(),
                self.frame_output_dir.text(),
            ),
            mask_output_dir=checked_path(
                self.mask_output_enabled.isChecked(),
                self.mask_output_dir.text(),
            ),
            ai_mask_output_dir=checked_path(
                self.ai_mask_output_enabled.isChecked(),
                self.ai_mask_output_dir.text(),
            ),
            color_key_mask_output_dir=checked_path(
                self.color_key_mask_output_enabled.isChecked(),
                self.color_key_mask_output_dir.text(),
            ),
            still_mask_output_path=checked_path(
                self.still_mask_output_enabled.isChecked(),
                self.still_mask_output_path.text(),
            ),
            report_output_path=checked_path(
                self.report_output_enabled.isChecked(),
                self.report_output_path.text(),
            ),
            contact_sheet_output_path=checked_path(
                self.contact_sheet_output_enabled.isChecked(),
                self.contact_sheet_output_path.text(),
            ),
            preview_output_path=checked_path(
                self.preview_output_enabled.isChecked(),
                self.preview_output_path.text(),
            ),
            area_jump_threshold=self.area_jump_threshold.value(),
            bbox_jump_threshold=self.bbox_jump_threshold.value(),
        )
        return output_path, options

    def _cleanup_options_from_ui(self) -> MaskCleanupOptions:
        return MaskCleanupOptions(
            enabled=self.cleanup_enabled.isChecked(),
            alpha_threshold=self.alpha_threshold.value()
            if self.alpha_threshold_enabled.isChecked()
            else None,
            min_artifact_size=self.min_artifact_size.value(),
            fill_hole_size=self.fill_hole_size.value(),
            keep_largest_component=self.keep_largest_component.isChecked(),
            feather_radius=self.feather_radius.value(),
        )

    def _command_preview_for(self, options: GuiProcessingOptions) -> str:
        if self.loaded_input is None:
            return ""
        output_text = self.output_path_input.text().strip()
        output_path = Path(output_text) if output_text else suggest_output_path(self.loaded_input.metadata.path)
        return build_command_preview(
            input_path=self.loaded_input.metadata.path,
            output_path=output_path,
            input_type=self.loaded_input.metadata.input_type,
            model_name=self.model_select.currentText(),
            overwrite=self.overwrite_output.isChecked(),
            options=options,
        )

    def _update_command_preview(self, *_args) -> None:
        if not hasattr(self, "command_preview"):
            return
        if self.loaded_input is None:
            self.command_preview.setPlainText("Load an input to preview the generated CLI command.")
            return
        try:
            _output_path, options = self._collect_processing_request()
        except ValueError as error:
            self.command_preview.setPlainText(f"Invalid settings: {error}")
            return
        self.command_preview.setPlainText(self._command_preview_for(options))

    def _show_validation_error(self, message: str) -> None:
        self.status_label.setText("Invalid settings")
        self.statusBar().showMessage(message)
        self.warnings_panel.setPlainText(message)

    def _fill_suggested_artifact_paths(self, input_path: Path) -> None:
        output_dir = input_path.parent / f"{input_path.stem}.artifacts"
        self.frame_output_dir.setText(str(output_dir / "frames"))
        self.mask_output_dir.setText(str(output_dir / "masks"))
        self.ai_mask_output_dir.setText(str(output_dir / "ai-masks"))
        self.color_key_mask_output_dir.setText(str(output_dir / "color-key-masks"))
        self.still_mask_output_path.setText(str(input_path.with_name(f"{input_path.stem}.mask.png")))
        self.report_output_path.setText(str(input_path.with_name(f"{input_path.stem}.report.json")))
        self.contact_sheet_output_path.setText(
            str(input_path.with_name(f"{input_path.stem}.contact.png"))
        )
        self.preview_output_path.setText(str(input_path.with_name(f"{input_path.stem}.preview.gif")))

    def _set_processing_state(self, processing: bool) -> None:
        self.open_action.setEnabled(not processing)
        self.validate_action.setEnabled(not processing)
        self.process_action.setEnabled(not processing and self.loaded_input is not None)
        self.save_as_action.setEnabled(not processing and self.loaded_input is not None)
        self.cancel_action.setEnabled(processing)
        self.model_select.setEnabled(not processing)
        self.preset_select.setEnabled(not processing)
        self.logging_select.setEnabled(not processing)
        self.cleanup_enabled.setEnabled(not processing)
        self.alpha_threshold_enabled.setEnabled(not processing)
        self.alpha_threshold.setEnabled(not processing and self.alpha_threshold_enabled.isChecked())
        self.min_artifact_size.setEnabled(not processing)
        self.fill_hole_size.setEnabled(not processing)
        self.keep_largest_component.setEnabled(not processing)
        self.feather_radius.setEnabled(not processing)
        self.color_key_sample_corners.setEnabled(not processing)
        self.color_key_color.setEnabled(not processing)
        self.color_key_tolerance.setEnabled(not processing)
        self.color_key_protect_alpha.setEnabled(not processing)
        self.overwrite_output.setEnabled(not processing)

    def _clear_worker_refs(self) -> None:
        self.processing_thread = None
        self.processing_worker = None

    def _update_model_metadata(self, *_args) -> None:
        if not hasattr(self, "model_metadata_label"):
            return
        self.model_metadata_label.setText(
            describe_model(
                self.model_select.currentText(),
                Path(self.cache_dir_input.text() or ".cache/rembg-models"),
            )
        )

    def _apply_preset(self, preset: str) -> None:
        if preset == "Stylized Character":
            self.model_select.setCurrentText("isnet-anime")
            self.cleanup_enabled.setChecked(True)
            self.keep_largest_component.setChecked(False)
        elif preset == "Fast Draft":
            self.model_select.setCurrentText("u2netp")
            self.cleanup_enabled.setChecked(True)
            self.keep_largest_component.setChecked(False)
        elif preset == "Raw Model Output":
            self.cleanup_enabled.setChecked(False)
            self.keep_largest_component.setChecked(False)
        else:
            self.model_select.setCurrentText("bria-rmbg")
            self.cleanup_enabled.setChecked(True)
            self.keep_largest_component.setChecked(preset == "Near-Solid Background")


class PreviewPane(QFrame):
    files_dropped = Signal(list)
    frame_changed = Signal(int)

    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self.setObjectName("previewPane")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)

        self.frames: list[PreviewFrame] = []
        self.current_frame_index = 0
        self.zoom_mode = "Fit"
        self.checkerboard_enabled = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.image_label = QLabel(placeholder)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setMinimumSize(QSize(240, 220))
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.image_label, stretch=1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_playback)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setEnabled(False)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.valueChanged.connect(self.set_frame_index)
        self.frame_label = QLabel("0 / 0")
        self.zoom_select = QComboBox()
        self.zoom_select.addItems(["Fit", "100%", "200%"])
        self.zoom_select.currentTextChanged.connect(self.set_zoom_mode)
        self.checkerboard = QCheckBox("Checker")
        self.checkerboard.setChecked(True)
        self.checkerboard.toggled.connect(self.set_checkerboard_enabled)
        controls.addWidget(self.play_button)
        controls.addWidget(self.frame_slider, stretch=1)
        controls.addWidget(self.frame_label)
        controls.addWidget(self.zoom_select)
        controls.addWidget(self.checkerboard)
        layout.addLayout(controls)
        self._apply_checkerboard()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if _event_has_files(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = _paths_from_drop(event)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render_current_frame()

    def set_message(self, message: str) -> None:
        self.stop_playback()
        self.frames = []
        self.current_frame_index = 0
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(message)
        self.frame_slider.setEnabled(False)
        self.frame_slider.setRange(0, 0)
        self.frame_label.setText("0 / 0")
        self.play_button.setEnabled(False)

    def set_frames(self, frames: list[PreviewFrame]) -> None:
        self.stop_playback()
        self.frames = frames
        self.current_frame_index = 0
        last_index = max(len(frames) - 1, 0)
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, last_index)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(len(frames) > 1)
        self.play_button.setEnabled(len(frames) > 1)
        self._render_current_frame()

    def toggle_playback(self) -> None:
        if self.timer.isActive():
            self.stop_playback()
            return
        if not self.frames:
            return
        self.play_button.setText("Pause")
        self.timer.start(max(self.frames[self.current_frame_index].duration_ms, 1))

    def stop_playback(self) -> None:
        self.timer.stop()
        if hasattr(self, "play_button"):
            self.play_button.setText("Play")

    def set_frame_index(self, index: int) -> None:
        if not self.frames:
            return
        self.current_frame_index = max(0, min(index, len(self.frames) - 1))
        self._render_current_frame()
        if self.timer.isActive():
            self.timer.start(max(self.frames[self.current_frame_index].duration_ms, 1))
        self.frame_changed.emit(self.current_frame_index)

    def set_zoom_mode(self, value: str) -> None:
        self.zoom_mode = value
        self._render_current_frame()

    def set_checkerboard_enabled(self, enabled: bool) -> None:
        self.checkerboard_enabled = enabled
        self._apply_checkerboard()

    def _advance_frame(self) -> None:
        if not self.frames:
            self.stop_playback()
            return
        self.set_frame_index((self.current_frame_index + 1) % len(self.frames))
        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(self.current_frame_index)
        self.frame_slider.blockSignals(False)

    def _render_current_frame(self) -> None:
        if not self.frames:
            return
        frame = self.frames[self.current_frame_index]
        image = QImage(
            frame.rgba,
            frame.width,
            frame.height,
            frame.width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
        pixmap = QPixmap.fromImage(_compose_preview_image(image, self.checkerboard_enabled))
        if self.zoom_mode == "Fit":
            pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        elif self.zoom_mode == "200%":
            pixmap = pixmap.scaled(
                frame.width * 2,
                frame.height * 2,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self.image_label.setText("")
        self.image_label.setPixmap(pixmap)
        self.frame_label.setText(f"{self.current_frame_index + 1} / {len(self.frames)}")

    def _apply_checkerboard(self) -> None:
        self.image_label.setStyleSheet(
            f"QLabel {{ background-color: {MOCHA['crust']}; border-radius: 6px; }}"
        )
        self._render_current_frame()


def _event_has_files(event: QDragEnterEvent | QDropEvent) -> bool:
    return event.mimeData().hasUrls()


def _paths_from_drop(event: QDragEnterEvent | QDropEvent) -> list[Path]:
    return [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]


def _format_metadata(loaded: LoadedInput) -> str:
    metadata = loaded.metadata
    parts = [
        f"File: {metadata.path.name}",
        f"Type: {metadata.input_type}",
        f"Dimensions: {metadata.width}x{metadata.height}",
        f"Frames: {metadata.frame_count}",
    ]
    if metadata.durations_ms:
        durations = ", ".join(str(duration) for duration in metadata.durations_ms[:12])
        if len(metadata.durations_ms) > 12:
            durations += ", ..."
        parts.append(f"Durations: {durations} ms")
    if metadata.input_type == "aseprite":
        parts.append(f"Layers: {metadata.layer_count}")
        parts.append(f"Tags: {', '.join(metadata.tags) if metadata.tags else 'none'}")
    return "\n".join(parts)


def _updated_recent_folders(existing: list[Path], folder: Path) -> list[Path]:
    folders = [folder] + [path for path in existing if path != folder]
    return folders[:8]


def _compose_preview_image(image: QImage, checkerboard: bool) -> QImage:
    background = QImage(image.size(), QImage.Format.Format_RGB32)
    if checkerboard:
        painter = QPainter(background)
        cell = 12
        light = QColor(MOCHA["surface0"])
        dark = QColor(MOCHA["mantle"])
        for y in range(0, image.height(), cell):
            for x in range(0, image.width(), cell):
                painter.fillRect(x, y, cell, cell, light if (x // cell + y // cell) % 2 == 0 else dark)
        painter.drawImage(0, 0, image)
        painter.end()
    else:
        background.fill(QColor(MOCHA["crust"]))
        painter = QPainter(background)
        painter.drawImage(0, 0, image)
        painter.end()
    return background
