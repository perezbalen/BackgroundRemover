"""GUI processing option collection and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from background_remover.color_key import ColorKeyOptions, parse_rgb_color
from background_remover.mask_cleanup import MaskCleanupOptions
from background_remover.processing import DEFAULT_MODEL_CACHE_DIR


@dataclass(frozen=True)
class GuiProcessingOptions:
    model_cache_dir: Path = Path(DEFAULT_MODEL_CACHE_DIR)
    quiet: bool = False
    verbose: int = 0
    cleanup_options: MaskCleanupOptions = MaskCleanupOptions()
    color_key_options: ColorKeyOptions = ColorKeyOptions()
    frame_output_dir: Path | None = None
    mask_output_dir: Path | None = None
    ai_mask_output_dir: Path | None = None
    color_key_mask_output_dir: Path | None = None
    still_mask_output_path: Path | None = None
    report_output_path: Path | None = None
    contact_sheet_output_path: Path | None = None
    preview_output_path: Path | None = None
    area_jump_threshold: float = 0.25
    bbox_jump_threshold: float = 32.0


def build_color_key_options(
    *,
    sample_corners: bool,
    color_text: str,
    tolerance: float,
    protect_alpha: int,
) -> ColorKeyOptions:
    color = None
    if color_text.strip():
        color = parse_rgb_color(color_text)
    return ColorKeyOptions(
        enabled=sample_corners or color is not None,
        sample_corners=sample_corners and color is None,
        color=color,
        tolerance=tolerance,
        protect_alpha=protect_alpha,
    )


def checked_path(enabled: bool, value: str) -> Path | None:
    if not enabled:
        return None
    text = value.strip()
    if not text:
        raise ValueError("enabled output paths must not be empty")
    return Path(text)
