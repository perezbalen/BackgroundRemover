from __future__ import annotations

import pytest
from PIL import Image

from background_remover.color_key import (
    ColorKeyOptions,
    apply_color_key_assist,
    build_color_key_mask,
    combine_ai_and_color_key_masks,
    parse_rgb_color,
    sample_corner_color,
)


def _rgba(width: int, height: int, values: list[tuple[int, int, int, int]]) -> Image.Image:
    image = Image.new("RGBA", (width, height))
    image.putdata(values)
    return image


def _mask(width: int, height: int, values: list[int]) -> Image.Image:
    image = Image.new("L", (width, height))
    image.putdata(values)
    return image


def test_parse_rgb_color_accepts_hex_and_csv() -> None:
    assert parse_rgb_color("#f0f1f2") == (240, 241, 242)
    assert parse_rgb_color("1, 2, 3") == (1, 2, 3)


def test_parse_rgb_color_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_rgb_color("300,0,0")


def test_sample_corner_color_averages_visible_corners() -> None:
    image = _rgba(
        2,
        2,
        [
            (10, 20, 30, 255),
            (20, 30, 40, 255),
            (30, 40, 50, 0),
            (30, 40, 50, 255),
        ],
    )

    assert sample_corner_color(image) == (20, 30, 40)


def test_build_color_key_mask_marks_near_background_as_transparent() -> None:
    image = _rgba(
        3,
        1,
        [
            (255, 255, 255, 255),
            (245, 245, 245, 255),
            (120, 0, 0, 255),
        ],
    )

    result = build_color_key_mask(image, (255, 255, 255), tolerance=20)

    assert list(result.tobytes()) == [0, 0, 255]


def test_combine_color_key_preserves_high_confidence_ai_foreground() -> None:
    ai_mask = _mask(3, 1, [20, 230, 180])
    color_key_mask = _mask(3, 1, [0, 0, 255])

    result = combine_ai_and_color_key_masks(
        ai_mask=ai_mask,
        color_key_mask=color_key_mask,
        protect_alpha=224,
    )

    assert list(result.tobytes()) == [0, 230, 180]


def test_apply_color_key_assist_can_sample_corners() -> None:
    image = _rgba(
        2,
        2,
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (40, 40, 40, 255),
        ],
    )
    ai_mask = _mask(2, 2, [128, 128, 128, 128])

    result = apply_color_key_assist(
        image,
        ai_mask,
        ColorKeyOptions(enabled=True, sample_corners=True, tolerance=10, protect_alpha=224),
    )

    assert result is not None
    assert result.background_color == (201, 201, 201)
    assert list(result.combined_mask.tobytes()) == [128, 128, 128, 128]
