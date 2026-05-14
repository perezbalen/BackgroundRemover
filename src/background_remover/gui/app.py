"""PySide6 GUI launcher."""

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
        from PySide6.QtWidgets import QApplication
    except ImportError as error:
        parser.exit(
            1,
            "error: missing GUI dependencies. Install with: "
            'python3 -m pip install -e ".[gui]"\n',
        )
        raise AssertionError("unreachable") from error

    from background_remover.gui.main_window import MainWindow
    from background_remover.gui.theme import apply_theme

    app = QApplication(sys.argv[:1])
    app.setOrganizationName("perezbalen")
    app.setApplicationName("Aseprite Background Remover")
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()
