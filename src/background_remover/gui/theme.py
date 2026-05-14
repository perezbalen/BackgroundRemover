"""Catppuccin Mocha theme for the desktop GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


MOCHA = {
    "rosewater": "#f5e0dc",
    "flamingo": "#f2cdcd",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
    "red": "#f38ba8",
    "maroon": "#eba0ac",
    "peach": "#fab387",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "teal": "#94e2d5",
    "sky": "#89dceb",
    "sapphire": "#74c7ec",
    "blue": "#89b4fa",
    "lavender": "#b4befe",
    "text": "#cdd6f4",
    "subtext1": "#bac2de",
    "subtext0": "#a6adc8",
    "overlay2": "#9399b2",
    "overlay1": "#7f849c",
    "overlay0": "#6c7086",
    "surface2": "#585b70",
    "surface1": "#45475a",
    "surface0": "#313244",
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
}


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 11))
    app.setPalette(_build_palette())
    app.setStyleSheet(_build_stylesheet())


def _build_palette() -> QPalette:
    palette = QPalette()
    base = QColor(MOCHA["base"])
    mantle = QColor(MOCHA["mantle"])
    surface0 = QColor(MOCHA["surface0"])
    surface1 = QColor(MOCHA["surface1"])
    text = QColor(MOCHA["text"])
    subtext0 = QColor(MOCHA["subtext0"])
    blue = QColor(MOCHA["blue"])
    red = QColor(MOCHA["red"])

    palette.setColor(QPalette.ColorRole.Window, base)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, mantle)
    palette.setColor(QPalette.ColorRole.AlternateBase, surface0)
    palette.setColor(QPalette.ColorRole.ToolTipBase, surface0)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, surface0)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, red)
    palette.setColor(QPalette.ColorRole.Link, blue)
    palette.setColor(QPalette.ColorRole.Highlight, blue)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(MOCHA["crust"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, subtext0)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, subtext0)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, surface1)
    return palette


def _build_stylesheet() -> str:
    c = MOCHA
    return f"""
QMainWindow, QWidget {{
    background-color: {c["base"]};
    color: {c["text"]};
    font-size: 11pt;
}}

QToolBar {{
    background-color: {c["mantle"]};
    border: 0;
    border-bottom: 1px solid {c["surface0"]};
    padding: 6px;
    spacing: 6px;
}}

QToolButton, QPushButton {{
    background-color: {c["surface0"]};
    color: {c["text"]};
    border: 1px solid {c["surface1"]};
    border-radius: 6px;
    padding: 7px 11px;
    min-height: 24px;
}}

QToolButton:hover, QPushButton:hover {{
    background-color: {c["surface1"]};
    border-color: {c["blue"]};
}}

QToolButton:pressed, QPushButton:pressed {{
    background-color: {c["surface2"]};
}}

QToolButton:disabled, QPushButton:disabled {{
    color: {c["overlay0"]};
    background-color: {c["mantle"]};
    border-color: {c["surface0"]};
}}

QGroupBox {{
    background-color: {c["mantle"]};
    border: 1px solid {c["surface0"]};
    border-radius: 8px;
    margin-top: 18px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}

QGroupBox::title {{
    color: {c["mauve"]};
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QFrame#previewPane, QFrame {{
    background-color: {c["mantle"]};
    border: 1px solid {c["surface0"]};
    border-radius: 8px;
}}

QLabel#previewTitle {{
    color: {c["lavender"]};
    font-size: 13pt;
    font-weight: 700;
}}

QLineEdit, QComboBox, QPlainTextEdit {{
    background-color: {c["crust"]};
    color: {c["text"]};
    border: 1px solid {c["surface1"]};
    border-radius: 6px;
    padding: 7px;
    selection-background-color: {c["blue"]};
    selection-color: {c["crust"]};
}}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border-color: {c["mauve"]};
}}

QComboBox::drop-down {{
    border: 0;
    width: 26px;
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid {c["surface2"]};
    background-color: {c["crust"]};
}}

QCheckBox::indicator:checked {{
    background-color: {c["green"]};
    border-color: {c["green"]};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {c["surface0"]};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {c["mauve"]};
    border: 1px solid {c["mauve"]};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QProgressBar {{
    background-color: {c["crust"]};
    color: {c["text"]};
    border: 1px solid {c["surface1"]};
    border-radius: 6px;
    min-height: 16px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {c["blue"]};
    border-radius: 5px;
}}

QStatusBar {{
    background-color: {c["mantle"]};
    color: {c["subtext1"]};
    border-top: 1px solid {c["surface0"]};
}}

QSplitter::handle {{
    background-color: {c["surface0"]};
}}
"""
