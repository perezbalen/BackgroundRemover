from __future__ import annotations

import pytest


def test_gui_entry_point_imports_without_qt_event_loop() -> None:
    from background_remover import gui

    assert callable(gui.main)


def test_gui_parser_exposes_version_without_qt_import() -> None:
    from background_remover.gui.app import build_parser

    parser = build_parser()

    assert parser.prog == "background-remover-gui"
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--version"])
    assert error.value.code == 0
