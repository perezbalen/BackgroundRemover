"""Processing reports and visual debug exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MaskFrameMetrics:
    frame_index: int
    alpha_sum: int
    foreground_pixels: int
    coverage: float
    bounding_box: dict[str, int] | None
    changed_pixels_from_previous: int | None = None
    changed_ratio_from_previous: float | None = None
    area_delta_from_previous: int | None = None
    area_delta_ratio_from_previous: float | None = None
    bbox_center_shift_from_previous: float | None = None


@dataclass(frozen=True)
class ProcessingWarning:
    frame_index: int
    warning_type: str
    message: str
    value: float
    threshold: float


def build_processing_report(
    *,
    input_path: str,
    output_path: str,
    model_name: str,
    cleanup: str,
    color_key: str,
    width: int,
    height: int,
    durations_ms: list[int],
    masks: list[Any],
    processing_seconds: float,
    total_seconds: float,
    area_jump_threshold: float = 0.25,
    bbox_jump_threshold: float = 32.0,
) -> dict[str, Any]:
    frame_metrics = compute_mask_metrics(masks)
    warnings = detect_temporal_warnings(
        frame_metrics,
        area_jump_threshold=area_jump_threshold,
        bbox_jump_threshold=bbox_jump_threshold,
    )
    frame_count = len(frame_metrics)
    return {
        "input": input_path,
        "output": output_path,
        "model": model_name,
        "cleanup": cleanup,
        "color_key": color_key,
        "canvas": {"width": width, "height": height},
        "frames": frame_count,
        "durations_ms": durations_ms,
        "timing": {
            "processing_seconds": round(processing_seconds, 4),
            "average_frame_seconds": round(processing_seconds / frame_count, 4)
            if frame_count
            else 0.0,
            "total_seconds": round(total_seconds, 4),
        },
        "thresholds": {
            "area_jump_ratio": area_jump_threshold,
            "bbox_jump_pixels": bbox_jump_threshold,
        },
        "frame_metrics": [asdict(metric) for metric in frame_metrics],
        "warnings": [asdict(warning) for warning in warnings],
    }


def compute_mask_metrics(masks: list[Any]) -> list[MaskFrameMetrics]:
    metrics: list[MaskFrameMetrics] = []
    previous_mask_values: list[int] | None = None
    previous_metric: MaskFrameMetrics | None = None

    for frame_index, mask in enumerate(masks):
        alpha_mask = mask.convert("L")
        width, height = alpha_mask.size
        values = list(alpha_mask.tobytes())
        alpha_sum = sum(values)
        foreground_pixels = sum(1 for value in values if value > 0)
        coverage = foreground_pixels / len(values) if values else 0.0
        bounding_box = _bounding_box(values, width, height)

        changed_pixels = None
        changed_ratio = None
        area_delta = None
        area_delta_ratio = None
        bbox_center_shift = None
        if previous_mask_values is not None and previous_metric is not None:
            changed_pixels = sum(
                1 for previous, current in zip(previous_mask_values, values) if previous != current
            )
            changed_ratio = changed_pixels / len(values) if values else 0.0
            area_delta = foreground_pixels - previous_metric.foreground_pixels
            baseline = max(previous_metric.foreground_pixels, 1)
            area_delta_ratio = area_delta / baseline
            bbox_center_shift = _bbox_center_shift(previous_metric.bounding_box, bounding_box)

        metric = MaskFrameMetrics(
            frame_index=frame_index,
            alpha_sum=alpha_sum,
            foreground_pixels=foreground_pixels,
            coverage=coverage,
            bounding_box=bounding_box,
            changed_pixels_from_previous=changed_pixels,
            changed_ratio_from_previous=changed_ratio,
            area_delta_from_previous=area_delta,
            area_delta_ratio_from_previous=area_delta_ratio,
            bbox_center_shift_from_previous=bbox_center_shift,
        )
        metrics.append(metric)
        previous_metric = metric
        previous_mask_values = values

    return metrics


def detect_temporal_warnings(
    metrics: list[MaskFrameMetrics],
    *,
    area_jump_threshold: float = 0.25,
    bbox_jump_threshold: float = 32.0,
) -> list[ProcessingWarning]:
    warnings = []
    for metric in metrics:
        area_delta_ratio = metric.area_delta_ratio_from_previous
        if area_delta_ratio is not None and abs(area_delta_ratio) > area_jump_threshold:
            warnings.append(
                ProcessingWarning(
                    frame_index=metric.frame_index,
                    warning_type="mask_area_jump",
                    message=(
                        f"Frame {metric.frame_index} mask area changed by "
                        f"{area_delta_ratio:.1%} from the previous frame"
                    ),
                    value=area_delta_ratio,
                    threshold=area_jump_threshold,
                )
            )

        bbox_shift = metric.bbox_center_shift_from_previous
        if bbox_shift is not None and bbox_shift > bbox_jump_threshold:
            warnings.append(
                ProcessingWarning(
                    frame_index=metric.frame_index,
                    warning_type="bounding_box_jump",
                    message=(
                        f"Frame {metric.frame_index} foreground bounding box center moved "
                        f"{bbox_shift:.1f}px from the previous frame"
                    ),
                    value=bbox_shift,
                    threshold=bbox_jump_threshold,
                )
            )
    return warnings


def write_processing_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_contact_sheet(path: str | Path, originals: list[Any], masks: list[Any], results: list[Any]) -> None:
    if not originals:
        return

    from PIL import Image, ImageDraw

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cell_width = 180
    label_height = 18
    padding = 8
    columns = 3
    rows = len(originals)
    sheet_width = columns * cell_width + (columns + 1) * padding
    sheet_height = rows * (cell_width + label_height + padding) + padding
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    labels = ("original", "mask", "result")
    for row, (original, mask, result) in enumerate(zip(originals, masks, results)):
        y = padding + row * (cell_width + label_height + padding)
        row_images = (
            original.convert("RGBA"),
            mask.convert("L").convert("RGBA"),
            result.convert("RGBA"),
        )
        for column, image in enumerate(row_images):
            x = padding + column * (cell_width + padding)
            thumbnail = _thumbnail(image, cell_width, cell_width)
            sheet.alpha_composite(thumbnail, (x, y + label_height))
            draw.text((x, y), f"{row:04d} {labels[column]}", fill=(0, 0, 0, 255))

    sheet.convert("RGB").save(output)


def write_gif_preview(path: str | Path, frames: list[Any], durations_ms: list[int]) -> None:
    if not frames:
        return

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    gif_frames = [frame.convert("RGBA") for frame in frames]
    gif_frames[0].save(
        output,
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations_ms,
        loop=0,
        disposal=2,
    )


def _bounding_box(values: list[int], width: int, height: int) -> dict[str, int] | None:
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1

    for index, value in enumerate(values):
        if value == 0:
            continue
        x = index % width
        y = index // width
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    if max_x < min_x or max_y < min_y:
        return None
    return {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x + 1,
        "height": max_y - min_y + 1,
    }


def _bbox_center_shift(previous: dict[str, int] | None, current: dict[str, int] | None) -> float | None:
    if previous is None or current is None:
        return None
    previous_x = previous["x"] + previous["width"] / 2
    previous_y = previous["y"] + previous["height"] / 2
    current_x = current["x"] + current["width"] / 2
    current_y = current["y"] + current["height"] / 2
    return ((current_x - previous_x) ** 2 + (current_y - previous_y) ** 2) ** 0.5


def _thumbnail(image: Any, width: int, height: int):
    from PIL import Image

    thumbnail = image.copy()
    thumbnail.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (242, 242, 242, 255))
    x = (width - thumbnail.width) // 2
    y = (height - thumbnail.height) // 2
    canvas.alpha_composite(thumbnail, (x, y))
    return canvas
