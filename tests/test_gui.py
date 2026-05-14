from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from background_remover.gui.input_loader import (
    is_supported_input_path,
    load_aseprite_input,
    load_still_input,
    split_supported_paths,
)


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


def test_catppuccin_mocha_theme_defines_expected_core_colors() -> None:
    from background_remover.gui.theme import MOCHA

    assert MOCHA["base"] == "#1e1e2e"
    assert MOCHA["text"] == "#cdd6f4"
    assert MOCHA["mauve"] == "#cba6f7"


def test_supported_input_path_validation() -> None:
    assert is_supported_input_path("sprite.aseprite")
    assert is_supported_input_path("image.PNG")
    assert not is_supported_input_path("notes.txt")


def test_split_supported_paths_uses_first_supported_and_reports_skipped() -> None:
    selected, skipped = split_supported_paths(
        [
            Path("notes.txt"),
            Path("sprite.aseprite"),
            Path("second.png"),
        ]
    )

    assert selected == Path("sprite.aseprite")
    assert skipped == [Path("notes.txt"), Path("second.png")]


def test_load_still_input_returns_metadata_and_rgba_frame(tmp_path: Path) -> None:
    input_path = tmp_path / "input.png"
    Image.new("RGB", (3, 2), (10, 20, 30)).save(input_path)

    loaded = load_still_input(input_path)

    assert loaded.metadata.input_type == "image"
    assert loaded.metadata.width == 3
    assert loaded.metadata.height == 2
    assert loaded.metadata.frame_count == 1
    assert len(loaded.frames) == 1
    assert len(loaded.frames[0].rgba) == 3 * 2 * 4


def test_load_aseprite_input_returns_metadata_and_flattened_frames() -> None:
    loaded = load_aseprite_input("images/sprite.aseprite")

    assert loaded.metadata.input_type == "aseprite"
    assert loaded.metadata.frame_count > 1
    assert loaded.metadata.layer_count > 0
    assert len(loaded.frames) == loaded.metadata.frame_count
    assert loaded.frames[0].duration_ms == loaded.metadata.durations_ms[0]
    assert loaded.metadata.warnings
