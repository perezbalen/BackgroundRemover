"""Main desktop window scaffold."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
from typing import Any

from background_remover import __version__
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
from background_remover.gui.worker import BenchmarkWorker, ProcessingWorker, RebuildNoopWorker
from background_remover.mask_cleanup import MaskCleanupOptions

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QThread,
    QSize,
    Qt,
    QSettings,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
)
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
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QApplication,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
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
        self.tool_thread: QThread | None = None
        self.tool_worker: Any | None = None
        self.processing_started_at = 0.0
        self.completed_frame_seconds: list[float] = []
        self.last_successful_output_path: Path | None = None
        self.last_processing_result: Any | None = None
        self.benchmark_results: list[Any] = []
        self.output_view_paths: dict[str, Path] = {}
        self.output_path_user_selected = False
        self.managed_temp_dir = tempfile.TemporaryDirectory(prefix="background-remover-gui-")

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
        self.about_action.triggered.connect(self.show_about_dialog)
        self.model_select.currentTextChanged.connect(self._update_model_metadata)
        self.cache_dir_input.textChanged.connect(self._update_model_metadata)
        self.preset_select.currentTextChanged.connect(self._apply_preset)
        self._update_model_metadata()
        self._update_command_preview()
        if _running_under_wsl():
            self.report_summary_label.setText("Windows Explorer drag/drop unavailable under WSL")
            self._set_warning_messages(
                [
                    "This GUI is running as a WSL/Linux Qt app. Windows Explorer drag/drop "
                    "requires launching the GUI with native Windows Python/Qt. Use Save As "
                    "as the fallback in WSL."
                ]
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_settings()
        self.managed_temp_dir.cleanup()
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
        self.output_drag_handle = OutputDragHandle()
        self.output_drag_handle.setEnabled(False)
        toolbar.addWidget(self.output_drag_handle)
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
        self.output_view_select = QComboBox()
        self.output_view_select.addItem("Result", "result")
        self.output_view_select.setEnabled(False)
        self.output_view_select.currentIndexChanged.connect(self._load_selected_output_view)

        self.input_preview = PreviewPane("Drop or open an input file")
        self.output_preview = PreviewPane("Output appears after processing")
        self.input_preview.files_dropped.connect(self.load_dropped_files)
        self.output_preview.setEnabled(False)

        layout.addWidget(input_title, 0, 0)
        layout.addWidget(output_title, 0, 1)
        layout.addWidget(self.output_view_select, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
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

        tools_group = QGroupBox("Optional Tools")
        tools_layout = QVBoxLayout(tools_group)
        self.rebuild_noop_button = QPushButton("Rebuild Without Removal")
        self.rebuild_noop_button.clicked.connect(self.rebuild_without_removal)
        tools_layout.addWidget(self.rebuild_noop_button)

        self.benchmark_model_list = QListWidget()
        self.benchmark_model_list.setMaximumHeight(150)
        for model_name in SUPPORTED_MODELS:
            item = QListWidgetItem(model_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = model_name in {"bria-rmbg", "u2netp", "isnet-anime"}
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.benchmark_model_list.addItem(item)
        tools_layout.addWidget(QLabel("Compare Models"))
        tools_layout.addWidget(self.benchmark_model_list)

        benchmark_folder_row = QHBoxLayout()
        self.benchmark_output_dir = QLineEdit()
        self.benchmark_output_dir.setPlaceholderText("Benchmark output folder")
        benchmark_folder_button = QPushButton("Browse")
        benchmark_folder_button.clicked.connect(lambda: self._choose_directory(self.benchmark_output_dir))
        benchmark_folder_row.addWidget(self.benchmark_output_dir, stretch=1)
        benchmark_folder_row.addWidget(benchmark_folder_button)
        tools_layout.addLayout(benchmark_folder_row)

        benchmark_action_row = QHBoxLayout()
        self.run_benchmark_button = QPushButton("Run Compare")
        self.run_benchmark_button.clicked.connect(self.run_model_benchmark)
        self.open_benchmark_output_button = QPushButton("Open Output")
        self.open_benchmark_output_button.clicked.connect(self.open_selected_benchmark_output)
        self.open_benchmark_mask_button = QPushButton("Open Mask")
        self.open_benchmark_mask_button.clicked.connect(self.open_selected_benchmark_mask)
        benchmark_action_row.addWidget(self.run_benchmark_button)
        benchmark_action_row.addWidget(self.open_benchmark_output_button)
        benchmark_action_row.addWidget(self.open_benchmark_mask_button)
        tools_layout.addLayout(benchmark_action_row)

        self.benchmark_results_table = QTableWidget(0, 4)
        self.benchmark_results_table.setHorizontalHeaderLabels(["Model", "Seconds", "Output", "Mask"])
        self.benchmark_results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.benchmark_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.benchmark_results_table.setMaximumHeight(160)
        tools_layout.addWidget(self.benchmark_results_table)

        layout.addWidget(model_group)
        layout.addWidget(logging_group)
        layout.addWidget(cleanup_group)
        layout.addWidget(color_group)
        layout.addWidget(output_group)
        layout.addWidget(artifacts_group)
        layout.addWidget(report_group)
        layout.addWidget(command_group)
        layout.addWidget(metadata_group)
        layout.addWidget(tools_group)
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

        review_row = QHBoxLayout()

        warning_column = QVBoxLayout()
        self.report_summary_label = QLabel("No processing report")
        self.report_summary_label.setWordWrap(True)
        self.warnings_panel = QListWidget()
        self.warnings_panel.setMaximumHeight(112)
        self.warnings_panel.itemActivated.connect(self._activate_warning_item)
        self.warnings_panel.itemClicked.connect(self._activate_warning_item)
        warning_column.addWidget(self.report_summary_label)
        warning_column.addWidget(self.warnings_panel)

        artifact_column = QVBoxLayout()
        artifact_header = QHBoxLayout()
        artifact_header.addWidget(QLabel("Generated Artifacts"))
        artifact_header.addStretch(1)
        self.reveal_artifact_button = QPushButton("Reveal")
        self.reveal_artifact_button.setEnabled(False)
        self.reveal_artifact_button.clicked.connect(self._reveal_selected_artifact)
        artifact_header.addWidget(self.reveal_artifact_button)
        self.artifacts_panel = QListWidget()
        self.artifacts_panel.setMaximumHeight(112)
        self.artifacts_panel.currentItemChanged.connect(self._update_reveal_button)
        self.artifacts_panel.itemActivated.connect(lambda item: self._reveal_artifact_item(item))
        artifact_column.addLayout(artifact_header)
        artifact_column.addWidget(self.artifacts_panel)

        review_row.addLayout(warning_column, stretch=3)
        review_row.addLayout(artifact_column, stretch=2)

        layout.addLayout(top_row)
        layout.addLayout(review_row)
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

    def show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            "About Aseprite Background Remover",
            _format_about_text(
                app_version=__version__,
                cli_version=__version__,
                python_version=sys.version.split()[0],
                model_cache_dir=Path(self.cache_dir_input.text() or ".cache/rembg-models"),
            ),
        )

    def rebuild_without_removal(self) -> None:
        if self.loaded_input is None:
            self._show_error("Load an .aseprite input before rebuilding.")
            return
        metadata = self.loaded_input.metadata
        if metadata.input_type != "aseprite":
            self._show_error("Rebuild Without Removal only supports .aseprite inputs.")
            return
        suggested = metadata.path.with_name(f"{metadata.path.stem}.rebuilt.aseprite")
        output_text, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Rebuild Without Removal",
            str(suggested),
            "Aseprite files (*.aseprite)",
        )
        if not output_text:
            return
        output_path = Path(output_text)
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

        self._set_tool_running(True, "Rebuilding without removal")
        worker = RebuildNoopWorker(metadata.path, output_path, overwrite=overwrite)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._handle_rebuild_completed)
        worker.failed.connect(self._handle_tool_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_tool_refs)
        self.tool_worker = worker
        self.tool_thread = thread
        thread.start()

    def run_model_benchmark(self) -> None:
        if self.loaded_input is None:
            self._show_error("Load a still image before comparing models.")
            return
        metadata = self.loaded_input.metadata
        if metadata.input_type != "image":
            self._show_error("Compare Models uses the still-image benchmark workflow.")
            return
        model_names = self._selected_benchmark_models()
        if not model_names:
            self._show_validation_error("Select at least one model to compare.")
            return
        output_dir_text = self.benchmark_output_dir.text().strip()
        output_dir = (
            Path(output_dir_text)
            if output_dir_text
            else metadata.path.parent / f"{metadata.path.stem}.benchmark"
        )
        if not output_dir_text:
            self.benchmark_output_dir.setText(str(output_dir))

        self._set_tool_running(True, "Comparing models")
        self.benchmark_results_table.setRowCount(0)
        self.benchmark_results = []
        worker = BenchmarkWorker(
            input_path=metadata.path,
            output_dir=output_dir,
            model_names=model_names,
            model_cache_dir=Path(self.cache_dir_input.text() or ".cache/rembg-models"),
            overwrite=self.overwrite_output.isChecked(),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._handle_benchmark_progress)
        worker.completed.connect(self._handle_benchmark_completed)
        worker.failed.connect(self._handle_tool_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_tool_refs)
        self.tool_worker = worker
        self.tool_thread = thread
        thread.start()

    def open_selected_benchmark_output(self) -> None:
        result = self._selected_benchmark_result()
        if result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_path.resolve())))

    def open_selected_benchmark_mask(self) -> None:
        result = self._selected_benchmark_result()
        if result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.mask_path.resolve())))

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

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if _event_has_files(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

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
            self._suggested_final_output_path()
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
            selected_path = Path(path)
            if self.last_successful_output_path and self.last_successful_output_path.exists():
                if not self._copy_successful_output_to(selected_path):
                    return
                self.output_path_input.setText(str(selected_path))
                self.output_path_user_selected = True
                self.statusBar().showMessage(f"Saved {selected_path}")
                self._set_drag_export_path(selected_path)
                self._populate_artifacts_after_save_as(selected_path)
                return
            self.output_path_user_selected = True
            self.output_path_input.setText(str(selected_path))

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
        self.last_successful_output_path = None
        self.last_processing_result = None
        self.output_path_user_selected = False
        self.output_view_paths = {}
        metadata = loaded.metadata
        self.input_preview.set_frames(loaded.frames)
        self.input_metadata_label.setText(_format_metadata(loaded))
        self.output_path_input.clear()
        self.output_path_input.setPlaceholderText(
            f"Save As destination, default export: {suggest_output_path(metadata.path).name}"
        )
        self._fill_suggested_artifact_paths(metadata.path)
        self.process_action.setEnabled(True)
        self.save_as_action.setEnabled(True)
        self.output_view_select.clear()
        self.output_view_select.addItem("Result", "result")
        self.output_view_select.setEnabled(False)
        self.output_preview.set_drag_file_path(None)
        self.output_drag_handle.set_file_path(None)
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
        self._set_warning_messages(warnings)
        self.report_summary_label.setText("Input loaded")
        self.artifacts_panel.clear()
        self.reveal_artifact_button.setEnabled(False)
        self._update_command_preview()

    def _show_error(self, message: str) -> None:
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.report_summary_label.setText("Error")
        self._set_warning_messages([message])
        self.input_preview.set_message(message)

    def validate_settings(self) -> None:
        try:
            _output_path, options = self._collect_processing_request()
        except ValueError as error:
            self._show_validation_error(str(error))
            return
        command = self._command_preview_for(options)
        self.report_summary_label.setText("Settings valid")
        self._set_warning_messages([command])
        self.status_label.setText("Valid")
        self.statusBar().showMessage("Settings are valid")

    def start_processing(self) -> None:
        if self.loaded_input is None:
            self._show_error("Load an input before processing.")
            return
        try:
            output_path, options = self._collect_processing_request(for_processing=True)
        except ValueError as error:
            self._show_validation_error(str(error))
            return

        overwrite = self.overwrite_output.isChecked() or not self.output_path_user_selected
        if self.output_path_user_selected and output_path.exists() and not overwrite:
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
        self._set_drag_export_path(None)

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
        self.last_processing_result = result
        self._populate_review_tools(result)
        self._populate_output_view_modes(result)
        self._set_drag_export_path(output_path)
        self._load_selected_output_view()

    def _handle_processing_failed(self, message: str) -> None:
        self._set_processing_state(False)
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.report_summary_label.setText("Processing failed")
        self._set_warning_messages([message])
        self._set_drag_export_path(None)

    def _handle_rebuild_completed(self, output_path: Path) -> None:
        self._set_tool_running(False, "Ready")
        self.status_label.setText("Rebuilt")
        self.statusBar().showMessage(f"Wrote {output_path}")
        self.report_summary_label.setText("Rebuild Without Removal complete")
        self._set_warning_messages([f"Wrote rebuilt .aseprite: {output_path}"])

    def _handle_benchmark_progress(self, model_name: str, index: int, total: int) -> None:
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(index - 1)
        self.status_label.setText(f"Benchmarking {model_name}")
        self.statusBar().showMessage(f"Model {index}/{total}")

    def _handle_benchmark_completed(self, results: list[Any]) -> None:
        self.benchmark_results = results
        self._populate_benchmark_results(results)
        self._set_tool_running(False, "Ready")
        self.progress_bar.setRange(0, max(len(results), 1))
        self.progress_bar.setValue(len(results))
        self.status_label.setText("Benchmark complete")
        self.statusBar().showMessage(f"Compared {len(results)} model(s)")
        self.report_summary_label.setText("Compare Models complete")
        self._set_warning_messages(
            [f"{result.model_name}: {result.seconds:.2f}s" for result in results]
        )

    def _handle_tool_failed(self, message: str) -> None:
        self._set_tool_running(False, "Ready")
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.report_summary_label.setText("Optional tool failed")
        self._set_warning_messages([message])

    def _load_output_preview(self, output_path: Path) -> None:
        try:
            loaded = load_input(output_path)
        except Exception as error:
            self._set_warning_messages([f"Could not load output preview: {error}"])
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

    def _set_warning_messages(self, messages: list[str]) -> None:
        self.warnings_panel.clear()
        for message in messages:
            if not message:
                continue
            self.warnings_panel.addItem(message)

    def _populate_review_tools(self, result: Any, output_path_override: Path | None = None) -> None:
        warnings = list(getattr(result, "warnings", []))
        self.warnings_panel.clear()
        if warnings:
            for warning in warnings:
                item = QListWidgetItem(_format_report_warning(warning))
                item.setData(Qt.ItemDataRole.UserRole, warning.get("frame_index"))
                self.warnings_panel.addItem(item)
        else:
            self.warnings_panel.addItem("No report warnings.")

        artifact_lines = _artifact_items(result.artifacts, output_path_override=output_path_override)
        self.artifacts_panel.clear()
        for label, path in artifact_lines:
            item = QListWidgetItem(f"{label}: {path}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.artifacts_panel.addItem(item)
        self.reveal_artifact_button.setEnabled(bool(artifact_lines))

        self.report_summary_label.setText(
            _format_output_summary(result, self.loaded_input, output_path_override)
        )

    def _populate_output_view_modes(self, result: Any) -> None:
        artifacts = result.artifacts
        self.output_view_paths = {"result": artifacts.output_path}
        self.output_view_select.blockSignals(True)
        self.output_view_select.clear()
        self.output_view_select.addItem("Result", "result")

        mode_specs = [
            ("final_mask", "Final Mask", artifacts.mask_output_dir or artifacts.mask_output_path),
            ("ai_mask", "AI Mask", artifacts.ai_mask_output_dir),
            ("color_key_mask", "Color-Key Mask", artifacts.color_key_mask_output_dir),
            ("contact_sheet", "Contact Sheet", artifacts.contact_sheet_output_path),
        ]
        for key, label, path in mode_specs:
            if path and _preview_path_available(path):
                self.output_view_paths[key] = path
                self.output_view_select.addItem(label, key)

        self.output_view_select.setEnabled(True)
        self.output_view_select.setCurrentIndex(0)
        self.output_view_select.blockSignals(False)

    def _load_selected_output_view(self, *_args) -> None:
        key = self.output_view_select.currentData()
        path = self.output_view_paths.get(str(key))
        if path is None:
            return
        if path.is_dir():
            durations = self.loaded_input.metadata.durations_ms if self.loaded_input else []
            frames = _load_png_sequence_preview(path, durations)
            if not frames:
                self.output_preview.set_message(f"No PNG frames found in {path}")
                return
            self.output_preview.setEnabled(True)
            self.output_preview.set_frames(frames)
            self._sync_output_to_input()
            return
        self._load_output_preview(path)

    def _activate_warning_item(self, item: QListWidgetItem) -> None:
        frame_index = item.data(Qt.ItemDataRole.UserRole)
        if frame_index is None:
            return
        try:
            index = int(frame_index)
        except (TypeError, ValueError):
            return
        self.input_preview.set_frame_index(index)
        self.output_preview.set_frame_index(index)

    def _update_reveal_button(self, current: QListWidgetItem | None) -> None:
        self.reveal_artifact_button.setEnabled(current is not None)

    def _reveal_selected_artifact(self) -> None:
        item = self.artifacts_panel.currentItem()
        if item is not None:
            self._reveal_artifact_item(item)

    def _reveal_artifact_item(self, item: QListWidgetItem) -> None:
        path_text = item.data(Qt.ItemDataRole.UserRole)
        if not path_text:
            return
        path = Path(str(path_text))
        target = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def _copy_successful_output_to(self, destination: Path) -> bool:
        if self.last_successful_output_path is None:
            return False
        source = self.last_successful_output_path
        if destination.exists() and destination.resolve() != source.resolve():
            answer = QMessageBox.question(
                self,
                "Replace Existing Output",
                f"{destination} already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        if destination.parent and str(destination.parent) != ".":
            destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() != source.resolve():
            shutil.copy2(source, destination)
        self.last_successful_output_path = destination
        return True

    def _set_drag_export_path(self, path: Path | None) -> None:
        enabled_path = path if path and path.exists() else None
        if enabled_path is not None and _running_under_wsl():
            message = (
                "Windows Explorer drag/drop is unavailable when the GUI is running under WSL. "
                "Use Save As, or launch the app with native Windows Python."
            )
            self.output_preview.set_drag_file_path(None)
            self.output_drag_handle.set_unavailable(message)
            return
        self.output_preview.set_drag_file_path(enabled_path)
        self.output_drag_handle.set_file_path(enabled_path)

    def _populate_artifacts_after_save_as(self, output_path: Path) -> None:
        if self.last_processing_result is None:
            return
        self.output_view_paths["result"] = output_path
        current_key = str(self.output_view_select.currentData())
        self._populate_review_tools(self.last_processing_result, output_path_override=output_path)
        result_index = self.output_view_select.findData(current_key)
        if result_index >= 0:
            self.output_view_select.setCurrentIndex(result_index)

    def _collect_processing_request(
        self,
        *,
        for_processing: bool = False,
    ) -> tuple[Path, GuiProcessingOptions]:
        if self.loaded_input is None:
            raise ValueError("Load an input before processing.")
        output_text = self.output_path_input.text().strip()
        if output_text:
            output_path = Path(output_text)
            self.output_path_user_selected = True
        elif for_processing:
            output_path = self._managed_temp_output_path()
        else:
            output_path = self._suggested_final_output_path()

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

    def _suggested_final_output_path(self) -> Path:
        if self.loaded_input is None:
            return Path()
        return suggest_output_path(self.loaded_input.metadata.path)

    def _managed_temp_output_path(self) -> Path:
        suggested = self._suggested_final_output_path()
        temp_dir = Path(self.managed_temp_dir.name)
        return temp_dir / suggested.name

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
        self.report_summary_label.setText("Invalid settings")
        self._set_warning_messages([message])

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
        self.output_view_select.setEnabled(not processing and bool(self.output_view_paths))
        self.reveal_artifact_button.setEnabled(
            not processing and self.artifacts_panel.currentItem() is not None
        )
        self.rebuild_noop_button.setEnabled(not processing)
        self.run_benchmark_button.setEnabled(not processing)

    def _clear_worker_refs(self) -> None:
        self.processing_thread = None
        self.processing_worker = None

    def _clear_tool_refs(self) -> None:
        self.tool_thread = None
        self.tool_worker = None

    def _set_tool_running(self, running: bool, message: str) -> None:
        self.open_action.setEnabled(not running)
        self.validate_action.setEnabled(not running)
        self.process_action.setEnabled(not running and self.loaded_input is not None)
        self.save_as_action.setEnabled(not running and self.loaded_input is not None)
        self.rebuild_noop_button.setEnabled(not running)
        self.run_benchmark_button.setEnabled(not running)
        self.cancel_action.setEnabled(False)
        self.progress_bar.setRange(0, 0 if running else 100)
        if not running:
            self.progress_bar.setValue(0)
        self.status_label.setText(message)
        self.statusBar().showMessage(message)

    def _selected_benchmark_models(self) -> list[str]:
        model_names = []
        for row in range(self.benchmark_model_list.count()):
            item = self.benchmark_model_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                model_names.append(item.text())
        return model_names

    def _populate_benchmark_results(self, results: list[Any]) -> None:
        self.benchmark_results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            values = [
                result.model_name,
                f"{result.seconds:.2f}",
                str(result.output_path),
                str(result.mask_path),
            ]
            for column, value in enumerate(values):
                self.benchmark_results_table.setItem(row, column, QTableWidgetItem(value))
        if results:
            self.benchmark_results_table.selectRow(0)

    def _selected_benchmark_result(self):
        selected = self.benchmark_results_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self.benchmark_results):
            return self.benchmark_results[row]
        return None

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


class OutputDragHandle(QPushButton):
    def __init__(self) -> None:
        super().__init__("No output")
        self.file_path: Path | None = None
        self.drag_start_position = QPoint()
        self.setToolTip("Process an output before dragging")
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_file_path(self, path: Path | None) -> None:
        self.file_path = path
        if path is None:
            self.setText("No output")
            self.setToolTip("Process an output before dragging")
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setEnabled(False)
            return
        self.setText(f"Drag {path.name}")
        self.setToolTip(str(path))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setEnabled(True)

    def set_unavailable(self, message: str) -> None:
        self.file_path = None
        self.setText("Drag unavailable")
        self.setToolTip(message)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setEnabled(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not _should_start_file_drag(event, self.drag_start_position):
            super().mouseMoveEvent(event)
            return
        if _start_file_drag(self, self.file_path):
            return
        super().mouseMoveEvent(event)


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
        self.drag_file_path: Path | None = None
        self.drag_start_position = QPoint()
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
        self.image_label.setAcceptDrops(True)
        self.image_label.installEventFilter(self)
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

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if _event_has_files(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = _paths_from_drop(event)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.image_label:
            if event.type() == QEvent.Type.DragEnter:
                drag_event = event
                if _event_has_files(drag_event):
                    drag_event.acceptProposedAction()
                    return True
            elif event.type() == QEvent.Type.DragMove:
                drag_event = event
                if _event_has_files(drag_event):
                    drag_event.acceptProposedAction()
                    return True
            elif event.type() == QEvent.Type.Drop:
                drop_event = event
                paths = _paths_from_drop(drop_event)
                if paths:
                    self.files_dropped.emit(paths)
                    drop_event.acceptProposedAction()
                    return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = event
                if mouse_event.button() == Qt.MouseButton.LeftButton:
                    self.drag_start_position = mouse_event.position().toPoint()
            elif event.type() == QEvent.Type.MouseMove:
                mouse_event = event
                if _should_start_file_drag(mouse_event, self.drag_start_position):
                    return _start_file_drag(self, self.drag_file_path)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not _should_start_file_drag(event, self.drag_start_position):
            super().mouseMoveEvent(event)
            return
        if _start_file_drag(self, self.drag_file_path):
            return
        super().mouseMoveEvent(event)

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

    def set_drag_file_path(self, path: Path | None) -> None:
        self.drag_file_path = path
        cursor = Qt.CursorShape.OpenHandCursor if path is not None else Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)
        self.image_label.setCursor(cursor)

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


def _event_has_files(event: QDragEnterEvent | QDragMoveEvent | QDropEvent | QEvent) -> bool:
    mime_data = event.mimeData()
    return (
        mime_data.hasUrls()
        or mime_data.hasText()
        or any(_is_windows_filename_mime_format(mime_format) for mime_format in mime_data.formats())
    )


def _should_start_file_drag(event: QMouseEvent, start_position: QPoint) -> bool:
    if not event.buttons() & Qt.MouseButton.LeftButton:
        return False
    distance = (event.position().toPoint() - start_position).manhattanLength()
    return distance >= QApplication.startDragDistance()


def _start_file_drag(source: QWidget, path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
    drag = QDrag(source)
    drag.setMimeData(mime_data)
    drag.exec(Qt.DropAction.CopyAction)
    return True


def _paths_from_drop(event: QDragEnterEvent | QDropEvent | QEvent) -> list[Path]:
    return _paths_from_mime_data(event.mimeData())


def _paths_from_mime_data(mime_data: QMimeData) -> list[Path]:
    paths: list[Path] = []
    if mime_data.hasUrls():
        paths.extend(_paths_from_urls(mime_data.urls()))
    if mime_data.hasText():
        paths.extend(_paths_from_mime_text(mime_data.text()))
    paths.extend(_paths_from_windows_mime_formats(mime_data))
    return _dedupe_paths(paths)


def _paths_from_urls(urls: list[QUrl]) -> list[Path]:
    paths: list[Path] = []
    for url in urls:
        if url.isLocalFile():
            paths.append(_path_from_drag_text(url.toLocalFile()))
    return paths


def _paths_from_mime_text(text: str) -> list[Path]:
    paths: list[Path] = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith("file:"):
            url = QUrl(value)
            if url.isLocalFile():
                paths.append(_path_from_drag_text(url.toLocalFile()))
            continue
        paths.append(_path_from_drag_text(value))
    return paths


def _paths_from_windows_mime_formats(mime_data: QMimeData) -> list[Path]:
    paths: list[Path] = []
    for mime_format in mime_data.formats():
        if not _is_windows_filename_mime_format(mime_format):
            continue
        raw = bytes(mime_data.data(mime_format))
        if "FileNameW" in mime_format:
            text = raw.decode("utf-16le", errors="ignore")
        else:
            text = raw.decode(errors="ignore")
        for value in text.split("\x00"):
            value = value.strip()
            if value:
                paths.append(_path_from_drag_text(value))
    return paths


def _is_windows_filename_mime_format(mime_format: str) -> bool:
    return (
        mime_format.startswith("application/x-qt-windows-mime")
        and ("FileNameW" in mime_format or "FileName" in mime_format)
    )


def _path_from_drag_text(value: str) -> Path:
    text = value.strip().strip('"')
    if len(text) >= 3 and text[1] == ":" and text[2] in {"\\", "/"}:
        if _running_under_wsl():
            drive = text[0].lower()
            rest = text[3:].replace("\\", "/")
            return Path(f"/mnt/{drive}/{rest}")
        return Path(text)
    if len(text) >= 4 and text[0] == "/" and text[2] == ":" and text[3] in {"\\", "/"}:
        if _running_under_wsl():
            drive = text[1].lower()
            rest = text[4:].replace("\\", "/")
            return Path(f"/mnt/{drive}/{rest}")
        return Path(text[1:])
    return Path(text)


def _running_under_wsl() -> bool:
    if os.name == "nt" or platform.system() != "Linux":
        return False
    try:
        version = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


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


def _format_about_text(
    *,
    app_version: str,
    cli_version: str,
    python_version: str,
    model_cache_dir: Path,
) -> str:
    return "\n".join(
        [
            "Aseprite Background Remover",
            f"App version: {app_version}",
            f"CLI version: {cli_version}",
            f"Python: {python_version}",
            f"Model cache: {model_cache_dir}",
        ]
    )


def _format_output_summary(
    result: Any,
    loaded_input: LoadedInput | None,
    output_path_override: Path | None = None,
) -> str:
    warning_count = len(getattr(result, "warnings", []))
    parts = [f"Report warnings: {warning_count}"]
    if hasattr(result, "width") and hasattr(result, "height") and hasattr(result, "frame_count"):
        parts.append(f"Output: {result.width}x{result.height}, {result.frame_count} frames")
    elif loaded_input is not None:
        metadata = loaded_input.metadata
        parts.append(f"Output: {metadata.width}x{metadata.height}, 1 frame")
    parts.append(f"Model: {result.model_name}")
    if output_path_override is not None:
        parts.append(f"Saved as: {output_path_override}")
    parts.append(f"Cleanup: {result.cleanup_description}")
    if hasattr(result, "color_key_description"):
        parts.append(f"Color key: {result.color_key_description}")
    if hasattr(result, "layer_policy"):
        parts.append(f"Layer policy: {result.layer_policy}")
    if hasattr(result, "metadata_policy"):
        policy = "; ".join(f"{key}: {value}" for key, value in result.metadata_policy.items())
        parts.append(f"Metadata: {policy}")
    parts.append(f"Processing time: {result.timings.processing_seconds:.2f}s")
    if result.timings.average_frame_seconds:
        parts.append(f"Average frame: {result.timings.average_frame_seconds:.2f}s")
    return "\n".join(parts)


def _format_report_warning(warning: dict[str, Any]) -> str:
    frame = warning.get("frame_index", "?")
    warning_type = str(warning.get("warning_type", "warning")).replace("_", " ")
    message = warning.get("message", "")
    return f"Frame {frame}: {warning_type} - {message}"


def _artifact_items(
    artifacts: Any,
    *,
    output_path_override: Path | None = None,
) -> list[tuple[str, Path]]:
    specs = [
        ("Output", output_path_override or artifacts.output_path),
        ("Still mask", artifacts.mask_output_path),
        ("Processed frames", artifacts.frame_output_dir),
        ("Final masks", artifacts.mask_output_dir),
        ("AI masks", artifacts.ai_mask_output_dir),
        ("Color-key masks", artifacts.color_key_mask_output_dir),
        ("JSON report", artifacts.report_output_path),
        ("Contact sheet", artifacts.contact_sheet_output_path),
        ("GIF preview", artifacts.preview_output_path),
    ]
    return [(label, path) for label, path in specs if path is not None]


def _preview_path_available(path: Path) -> bool:
    if path.is_dir():
        return any(path.glob("*.png"))
    return path.exists()


def _load_png_sequence_preview(directory: Path, durations_ms: list[int] | None = None) -> list[PreviewFrame]:
    from PIL import Image

    frames: list[PreviewFrame] = []
    paths = sorted(directory.glob("*.png"))
    durations = durations_ms or []
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            duration_ms = durations[index] if index < len(durations) else 100
            frames.append(
                PreviewFrame(
                    width=rgba.width,
                    height=rgba.height,
                    rgba=rgba.tobytes(),
                    duration_ms=duration_ms,
                )
            )
    return frames


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
