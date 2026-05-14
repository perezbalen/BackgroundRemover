"""Main desktop window scaffold."""

from __future__ import annotations

from pathlib import Path

from background_remover.background import SUPPORTED_MODELS
from background_remover.gui.input_loader import (
    LoadedInput,
    PreviewFrame,
    is_supported_input_path,
    load_input,
    split_supported_paths,
)
from background_remover.gui.settings import GuiSettings
from background_remover.gui.theme import MOCHA

from PySide6.QtCore import QSize, Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
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

        self.setWindowTitle("Aseprite Background Remover")
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        self._create_actions()
        self._create_toolbar()
        self._create_workspace()
        self._create_status_bar()
        self._restore_settings()
        self.open_action.triggered.connect(self.open_input_file)

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
        panel = QWidget()
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        model_group = QGroupBox("Model")
        model_layout = QVBoxLayout(model_group)
        self.model_select = QComboBox()
        self.model_select.addItems(SUPPORTED_MODELS)
        model_layout.addWidget(self.model_select)

        cache_row = QHBoxLayout()
        self.cache_dir_input = QLineEdit()
        self.cache_dir_input.setPlaceholderText(".cache/rembg-models")
        cache_button = QPushButton("Browse")
        cache_row.addWidget(self.cache_dir_input, stretch=1)
        cache_row.addWidget(cache_button)
        model_layout.addLayout(cache_row)

        cleanup_group = QGroupBox("Cleanup")
        cleanup_layout = QVBoxLayout(cleanup_group)
        self.cleanup_enabled = QCheckBox("Enabled")
        self.cleanup_enabled.setChecked(True)
        self.keep_largest_component = QCheckBox("Keep largest component")
        cleanup_layout.addWidget(self.cleanup_enabled)
        cleanup_layout.addWidget(self.keep_largest_component)

        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Choose Save As before final export")
        output_layout.addWidget(self.output_path_input)

        metadata_group = QGroupBox("Input Metadata")
        metadata_layout = QVBoxLayout(metadata_group)
        self.input_metadata_label = QLabel("No input loaded")
        self.input_metadata_label.setWordWrap(True)
        metadata_layout.addWidget(self.input_metadata_label)

        layout.addWidget(model_group)
        layout.addWidget(cleanup_group)
        layout.addWidget(output_group)
        layout.addWidget(metadata_group)
        layout.addStretch(1)
        return panel

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
        metadata = loaded.metadata
        self.input_preview.set_frames(loaded.frames)
        self.input_metadata_label.setText(_format_metadata(loaded))
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

    def _show_error(self, message: str) -> None:
        self.status_label.setText("Error")
        self.statusBar().showMessage(message)
        self.warnings_panel.setPlainText(message)
        self.input_preview.set_message(message)


class PreviewPane(QFrame):
    from PySide6.QtCore import Signal

    files_dropped = Signal(list)

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
