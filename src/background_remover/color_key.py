"""Color-key assisted mask generation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


@dataclass(frozen=True)
class ColorKeyOptions:
    enabled: bool = False
    sample_corners: bool = False
    color: tuple[int, int, int] | None = None
    tolerance: float = 24.0
    protect_alpha: int = 224


@dataclass(frozen=True)
class ColorKeyResult:
    background_color: tuple[int, int, int]
    color_key_mask: "PILImage"
    combined_mask: "PILImage"


def parse_rgb_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 6 and all(character in "0123456789abcdefABCDEF" for character in text):
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError("color must be '#RRGGBB' or 'R,G,B'")

    try:
        color = tuple(int(part) for part in parts)
    except ValueError as error:
        raise ValueError("color channels must be integers") from error

    if any(channel < 0 or channel > 255 for channel in color):
        raise ValueError("color channels must be between 0 and 255")
    return color


def apply_color_key_assist(
    image: "PILImage",
    ai_mask: "PILImage",
    options: ColorKeyOptions,
) -> ColorKeyResult | None:
    if not options.enabled:
        return None

    _validate_options(options)
    background_color = options.color
    if background_color is None:
        if not options.sample_corners:
            raise ValueError("color key requires a user color or corner sampling")
        background_color = sample_corner_color(image)

    color_key_mask = build_color_key_mask(image, background_color, options.tolerance)
    combined_mask = combine_ai_and_color_key_masks(
        ai_mask=ai_mask,
        color_key_mask=color_key_mask,
        protect_alpha=options.protect_alpha,
    )
    return ColorKeyResult(
        background_color=background_color,
        color_key_mask=color_key_mask,
        combined_mask=combined_mask,
    )


def sample_corner_color(image: "PILImage") -> tuple[int, int, int]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    corners = [
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    ]
    visible = [pixel for pixel in corners if pixel[3] > 0]
    samples = visible or corners
    return tuple(round(sum(pixel[channel] for pixel in samples) / len(samples)) for channel in range(3))


def build_color_key_mask(
    image: "PILImage",
    background_color: tuple[int, int, int],
    tolerance: float,
) -> "PILImage":
    from PIL import Image

    rgba = image.convert("RGBA")
    output = Image.new("L", rgba.size)
    output_values = []
    pixels = rgba.tobytes()
    for index in range(0, len(pixels), 4):
        red, green, blue, alpha = pixels[index : index + 4]
        distance = _rgb_distance((red, green, blue), background_color)
        output_values.append(0 if alpha > 0 and distance <= tolerance else 255)
    output.putdata(output_values)
    return output


def combine_ai_and_color_key_masks(
    *,
    ai_mask: "PILImage",
    color_key_mask: "PILImage",
    protect_alpha: int,
) -> "PILImage":
    ai_values = list(ai_mask.convert("L").tobytes())
    key_values = list(color_key_mask.convert("L").tobytes())
    if len(ai_values) != len(key_values):
        raise ValueError("AI mask and color-key mask sizes do not match")

    combined = ai_mask.convert("L").copy()
    output = []
    for ai_alpha, key_alpha in zip(ai_values, key_values):
        if key_alpha == 0 and ai_alpha < protect_alpha:
            output.append(0)
        else:
            output.append(ai_alpha)
    combined.putdata(output)
    return combined


def describe_color_key_options(options: ColorKeyOptions) -> str:
    if not options.enabled:
        return "disabled"
    source = "corners" if options.sample_corners else "color"
    color = "sampled" if options.color is None else "#{:02x}{:02x}{:02x}".format(*options.color)
    return (
        f"source={source}, color={color}, tolerance={options.tolerance:g}, "
        f"protect_alpha={options.protect_alpha}"
    )


def _validate_options(options: ColorKeyOptions) -> None:
    if options.tolerance < 0:
        raise ValueError("color-key tolerance must be greater than or equal to 0")
    if not 0 <= options.protect_alpha <= 255:
        raise ValueError("color-key protect alpha must be between 0 and 255")
    if options.color is not None and any(channel < 0 or channel > 255 for channel in options.color):
        raise ValueError("color-key color channels must be between 0 and 255")


def _rgb_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))
