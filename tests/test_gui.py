from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from background_remover.gui.input_loader import (
    is_supported_input_path,
    load_aseprite_input,
    load_still_input,
    split_supported_paths,
)
from background_remover.gui.command_preview import build_command_preview
from background_remover.gui.output_paths import suggest_output_path
from background_remover.gui.processing_options import (
    GuiProcessingOptions,
    build_color_key_options,
    checked_path,
)
from background_remover.mask_cleanup import MaskCleanupOptions


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


def test_model_metadata_mentions_cache_and_license(tmp_path: Path) -> None:
    from background_remover.gui.model_metadata import describe_model

    description = describe_model("bria-rmbg", tmp_path)

    assert "Expected CPU cost: slow" in description
    assert "Cache: not cached" in description
    assert "license" in description.lower()


def test_suggest_output_path_uses_input_type_conventions() -> None:
    assert suggest_output_path(Path("images/susan.png")) == Path("images/susan.transparent.png")
    assert suggest_output_path(Path("images/sprite.aseprite")) == Path(
        "images/sprite.processed.aseprite"
    )


def test_color_key_options_parse_hex_and_enable_explicit_color() -> None:
    options = build_color_key_options(
        sample_corners=True,
        color_text="#ffffff",
        tolerance=12.5,
        protect_alpha=200,
    )

    assert options.enabled
    assert not options.sample_corners
    assert options.color == (255, 255, 255)
    assert options.tolerance == 12.5
    assert options.protect_alpha == 200


def test_checked_path_requires_value_when_enabled() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        checked_path(True, "")
    assert checked_path(False, "") is None


def test_command_preview_includes_full_aseprite_flags() -> None:
    command = build_command_preview(
        input_path=Path("images/sprite.aseprite"),
        output_path=Path("output/sprite.processed.aseprite"),
        input_type="aseprite",
        model_name="bria-rmbg",
        overwrite=True,
        options=GuiProcessingOptions(
            cleanup_options=MaskCleanupOptions(
                alpha_threshold=8,
                min_artifact_size=4,
                fill_hole_size=2,
                keep_largest_component=True,
                feather_radius=0.5,
            ),
            frame_output_dir=Path("output/frames"),
            mask_output_dir=Path("output/masks"),
            ai_mask_output_dir=Path("output/ai"),
            color_key_mask_output_dir=Path("output/key"),
            report_output_path=Path("output/report.json"),
            contact_sheet_output_path=Path("output/contact.png"),
            preview_output_path=Path("output/preview.gif"),
            color_key_options=build_color_key_options(
                sample_corners=False,
                color_text="#ffffff",
                tolerance=24,
                protect_alpha=224,
            ),
        ),
    )

    assert "--frame-output-dir output/frames" in command
    assert "--color-key-color '#ffffff'" in command
    assert "--keep-largest-component" in command
    assert "--preview-output output/preview.gif" in command


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


def test_gui_report_warning_format_mentions_warning_type_and_frame() -> None:
    from background_remover.gui.main_window import _format_report_warning

    text = _format_report_warning(
        {
            "frame_index": 3,
            "warning_type": "mask_area_jump",
            "message": "Frame 3 mask area changed by 40.0% from the previous frame",
        }
    )

    assert text.startswith("Frame 3: mask area jump")
    assert "40.0%" in text


def test_gui_artifact_items_include_only_generated_paths() -> None:
    from background_remover.gui.main_window import _artifact_items

    items = _artifact_items(
        SimpleNamespace(
            output_path=Path("out.aseprite"),
            mask_output_path=None,
            frame_output_dir=Path("frames"),
            mask_output_dir=None,
            ai_mask_output_dir=None,
            color_key_mask_output_dir=None,
            report_output_path=Path("report.json"),
            contact_sheet_output_path=None,
            preview_output_path=None,
        )
    )

    assert items == [
        ("Output", Path("out.aseprite")),
        ("Processed frames", Path("frames")),
        ("JSON report", Path("report.json")),
    ]
