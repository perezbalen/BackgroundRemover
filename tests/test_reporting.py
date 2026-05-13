from __future__ import annotations

import json

from PIL import Image

from background_remover.reporting import (
    build_processing_report,
    compute_mask_metrics,
    detect_temporal_warnings,
    write_contact_sheet,
    write_gif_preview,
    write_processing_report,
)


def _mask(width: int, height: int, values: list[int]) -> Image.Image:
    image = Image.new("L", (width, height))
    image.putdata(values)
    return image


def test_compute_mask_metrics_includes_diffs_area_and_bbox_shift() -> None:
    masks = [
        _mask(4, 4, [255, 255, 0, 0] + [0] * 12),
        _mask(4, 4, [0] * 10 + [255, 255, 255, 255, 0, 0]),
    ]

    metrics = compute_mask_metrics(masks)

    assert metrics[0].foreground_pixels == 2
    assert metrics[0].bounding_box == {"x": 0, "y": 0, "width": 2, "height": 1}
    assert metrics[1].foreground_pixels == 4
    assert metrics[1].changed_pixels_from_previous == 6
    assert metrics[1].area_delta_from_previous == 2
    assert metrics[1].area_delta_ratio_from_previous == 1.0
    assert metrics[1].bbox_center_shift_from_previous is not None
    assert metrics[1].bbox_center_shift_from_previous > 2.0


def test_detect_temporal_warnings_flags_area_and_bbox_jumps() -> None:
    metrics = compute_mask_metrics(
        [
            _mask(6, 6, [255, 255] + [0] * 34),
            _mask(6, 6, [0] * 28 + [255, 255, 255, 255] + [0] * 4),
        ]
    )

    warnings = detect_temporal_warnings(
        metrics,
        area_jump_threshold=0.5,
        bbox_jump_threshold=2.0,
    )

    assert [warning.warning_type for warning in warnings] == [
        "mask_area_jump",
        "bounding_box_jump",
    ]


def test_build_and_write_processing_report(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    report = build_processing_report(
        input_path="input.aseprite",
        output_path="output.aseprite",
        model_name="u2netp",
        cleanup="disabled",
        width=2,
        height=2,
        durations_ms=[83],
        masks=[_mask(2, 2, [0, 255, 0, 0])],
        processing_seconds=1.25,
        total_seconds=2.5,
    )

    write_processing_report(report_path, report)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["frames"] == 1
    assert saved["frame_metrics"][0]["coverage"] == 0.25
    assert saved["warnings"] == []


def test_visual_exports_create_files(tmp_path) -> None:
    originals = [Image.new("RGBA", (8, 8), (255, 0, 0, 255))]
    masks = [_mask(8, 8, [255] * 64)]
    results = [Image.new("RGBA", (8, 8), (0, 255, 0, 255))]
    contact_sheet = tmp_path / "contact.png"
    preview = tmp_path / "preview.gif"

    write_contact_sheet(contact_sheet, originals, masks, results)
    write_gif_preview(preview, results, [83])

    assert contact_sheet.exists()
    assert preview.exists()
