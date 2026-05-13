from __future__ import annotations

from PIL import Image

from background_remover.mask_cleanup import MaskCleanupOptions, apply_alpha_mask, apply_mask_cleanup


def _mask(width: int, height: int, values: list[int]) -> Image.Image:
    image = Image.new("L", (width, height))
    image.putdata(values)
    return image


def _rgba(width: int, height: int, values: list[tuple[int, int, int, int]]) -> Image.Image:
    image = Image.new("RGBA", (width, height))
    image.putdata(values)
    return image


def _values(image: Image.Image) -> list[int]:
    return list(image.tobytes())


def test_alpha_threshold_binarizes_mask() -> None:
    mask = _mask(4, 1, [0, 20, 120, 255])

    result = apply_mask_cleanup(mask, MaskCleanupOptions(alpha_threshold=100))

    assert _values(result) == [0, 0, 255, 255]


def test_remove_small_alpha_artifacts() -> None:
    mask = _mask(
        5,
        5,
        [
            255,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            255,
            255,
            0,
            0,
            0,
            255,
            255,
            0,
            0,
            0,
            0,
            0,
            0,
        ],
    )

    result = apply_mask_cleanup(mask, MaskCleanupOptions(min_artifact_size=2))

    values = _values(result)
    assert values[0] == 0
    assert values[12:14] == [255, 255]
    assert values[17:19] == [255, 255]


def test_fill_small_enclosed_holes() -> None:
    mask = _mask(
        5,
        5,
        [
            0,
            0,
            0,
            0,
            0,
            0,
            255,
            255,
            255,
            0,
            0,
            255,
            0,
            255,
            0,
            0,
            255,
            255,
            255,
            0,
            0,
            0,
            0,
            0,
            0,
        ],
    )

    result = apply_mask_cleanup(mask, MaskCleanupOptions(fill_hole_size=1))

    assert _values(result)[12] == 255


def test_keep_largest_foreground_component() -> None:
    mask = _mask(
        5,
        3,
        [
            255,
            0,
            0,
            0,
            0,
            255,
            0,
            255,
            255,
            0,
            0,
            0,
            255,
            255,
            0,
        ],
    )

    result = apply_mask_cleanup(mask, MaskCleanupOptions(keep_largest_component=True))

    assert _values(result) == [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        255,
        255,
        0,
        0,
        0,
        255,
        255,
        0,
    ]


def test_feather_radius_softens_cleaned_edge() -> None:
    mask = _mask(3, 1, [0, 255, 0])

    result = apply_mask_cleanup(mask, MaskCleanupOptions(feather_radius=1.0))

    values = _values(result)
    assert values[0] > 0
    assert values[1] < 255


def test_disabled_cleanup_returns_raw_alpha() -> None:
    mask = _mask(4, 1, [0, 10, 120, 255])

    result = apply_mask_cleanup(
        mask,
        MaskCleanupOptions(
            enabled=False,
            alpha_threshold=100,
            min_artifact_size=10,
            fill_hole_size=10,
            keep_largest_component=True,
            feather_radius=2.0,
        ),
    )

    assert _values(result) == [0, 10, 120, 255]


def test_apply_alpha_mask_bleeds_foreground_rgb_into_soft_edge_pixels() -> None:
    image = _rgba(
        3,
        1,
        [
            (180, 40, 20, 255),
            (255, 247, 237, 64),
            (255, 247, 237, 0),
        ],
    )
    mask = _mask(3, 1, [255, 64, 0])

    result = apply_alpha_mask(image, mask)

    assert result.getpixel((1, 0)) == (180, 40, 20, 64)
