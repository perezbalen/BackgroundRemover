from __future__ import annotations

from PIL import Image

from background_remover.background import RemovalResult, clean_removal_result
from background_remover.mask_cleanup import MaskCleanupOptions


def _rgba(width: int, height: int, values: list[tuple[int, int, int, int]]) -> Image.Image:
    image = Image.new("RGBA", (width, height))
    image.putdata(values)
    return image


def _mask(width: int, height: int, values: list[int]) -> Image.Image:
    image = Image.new("L", (width, height))
    image.putdata(values)
    return image


def test_clean_removal_result_uses_model_rgb_for_filled_mask_pixels() -> None:
    model_image = _rgba(
        3,
        3,
        [
            (190, 40, 30, 255),
            (190, 40, 30, 255),
            (190, 40, 30, 255),
            (190, 40, 30, 255),
            (0, 0, 0, 0),
            (190, 40, 30, 255),
            (190, 40, 30, 255),
            (190, 40, 30, 255),
            (190, 40, 30, 255),
        ],
    )
    model_mask = _mask(
        3,
        3,
        [
            255,
            255,
            255,
            255,
            0,
            255,
            255,
            255,
            255,
        ],
    )
    result = RemovalResult(image=model_image, mask=model_mask, elapsed_seconds=0.0)

    cleaned = clean_removal_result(
        result,
        MaskCleanupOptions(fill_hole_size=1),
    )

    assert cleaned.image.getpixel((1, 1)) == (190, 40, 30, 255)


def test_disabled_cleanup_returns_raw_model_output() -> None:
    model_image = _rgba(1, 1, [(0, 0, 0, 0)])
    model_mask = _mask(1, 1, [0])
    result = RemovalResult(image=model_image, mask=model_mask, elapsed_seconds=0.0)

    cleaned = clean_removal_result(result, MaskCleanupOptions(enabled=False))

    assert cleaned.image.getpixel((0, 0)) == (0, 0, 0, 0)
