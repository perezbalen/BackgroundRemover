"""Main desktop window scaffold."""

from __future__ import annotations

from pathlib import Path

from background_remover.background import SUPPORTED_MODELS
from background_remover.gui.settings import GuiSettings

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

        layout.addWidget(model_group)
        layout.addWidget(cleanup_group)
        layout.addWidget(output_group)
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


class PreviewPane(QFrame):
    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self.setObjectName("previewPane")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.placeholder = QLabel(placeholder)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        layout.addWidget(self.placeholder, stretch=1)
