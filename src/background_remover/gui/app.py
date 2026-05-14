"""Minimal PySide6 GUI launcher.

Phase 0 only establishes the dependency and command boundary. The full window,
preview, settings, and worker implementation are tracked in later GUI phases.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from background_remover import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="background-remover-gui",
        description="Launch the Aseprite Background Remover desktop GUI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError as error:
        parser.exit(
            1,
            "error: missing GUI dependencies. Install with: "
            'python3 -m pip install -e ".[gui]"\n',
        )
        raise AssertionError("unreachable") from error

    app = QApplication(sys.argv[:1])
    window = QMainWindow()
    window.setWindowTitle("Aseprite Background Remover")
    window.resize(960, 640)

    placeholder = QLabel("Aseprite Background Remover GUI")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(placeholder)

    window.show()
    return app.exec()
