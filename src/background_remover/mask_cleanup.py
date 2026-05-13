"""Alpha-mask cleanup helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class MaskCleanupOptions:
    enabled: bool = True
    alpha_threshold: int | None = None
    min_artifact_size: int = 0
    fill_hole_size: int = 0
    keep_largest_component: bool = False
    feather_radius: float = 0.0


def apply_mask_cleanup(mask, options: MaskCleanupOptions):
    """Return a cleaned L-mode alpha mask."""

    from PIL import ImageFilter

    cleaned = mask.convert("L")
    if not options.enabled:
        return cleaned.copy()

    _validate_options(options)

    width, height = cleaned.size
    alpha = list(cleaned.tobytes())
    threshold = options.alpha_threshold if options.alpha_threshold is not None else 1
    foreground = [value >= threshold for value in alpha]

    if options.min_artifact_size > 0:
        foreground = _remove_small_components(foreground, width, height, options.min_artifact_size)

    if options.keep_largest_component:
        foreground = _keep_largest_component(foreground, width, height)

    filled_holes: set[int] = set()
    if options.fill_hole_size > 0:
        foreground, filled_holes = _fill_small_holes(foreground, width, height, options.fill_hole_size)

    output = []
    for index, keep in enumerate(foreground):
        if not keep:
            output.append(0)
        elif index in filled_holes:
            output.append(255)
        elif options.alpha_threshold is not None:
            output.append(255)
        else:
            output.append(alpha[index])

    result = cleaned.copy()
    result.putdata(output)

    if options.feather_radius > 0:
        result = result.filter(ImageFilter.GaussianBlur(radius=options.feather_radius))

    return result


def apply_alpha_mask(image, mask):
    """Return an RGBA copy of image with mask as the alpha channel."""

    rgba = image.convert("RGBA")
    source_alpha = rgba.getchannel("A")
    alpha = mask.convert("L")
    rgba.putalpha(alpha)
    _bleed_foreground_rgb_into_soft_alpha(rgba, source_alpha)
    return rgba


def _bleed_foreground_rgb_into_soft_alpha(image, alpha, source_threshold: int = 224) -> None:
    width, height = image.size
    alpha_values = list(alpha.tobytes())
    pixels = bytearray(image.tobytes())
    visited = [False] * len(alpha_values)
    queue: deque[int] = deque()

    for index, value in enumerate(alpha_values):
        if value >= source_threshold:
            visited[index] = True
            queue.append(index)

    if not queue:
        return

    while queue:
        source_index = queue.popleft()
        source_offset = source_index * 4
        for neighbor in _neighbors(source_index, width, height):
            if visited[neighbor]:
                continue
            visited[neighbor] = True
            neighbor_offset = neighbor * 4
            pixels[neighbor_offset : neighbor_offset + 3] = pixels[
                source_offset : source_offset + 3
            ]
            queue.append(neighbor)

    image.frombytes(bytes(pixels))


def _validate_options(options: MaskCleanupOptions) -> None:
    if options.alpha_threshold is not None and not 0 <= options.alpha_threshold <= 255:
        raise ValueError("alpha_threshold must be between 0 and 255")
    if options.min_artifact_size < 0:
        raise ValueError("min_artifact_size must be greater than or equal to 0")
    if options.fill_hole_size < 0:
        raise ValueError("fill_hole_size must be greater than or equal to 0")
    if options.feather_radius < 0:
        raise ValueError("feather_radius must be greater than or equal to 0")


def _remove_small_components(
    foreground: list[bool],
    width: int,
    height: int,
    min_size: int,
) -> list[bool]:
    output = foreground.copy()
    for component in _components(foreground, width, height, target=True):
        if len(component) < min_size:
            for index in component:
                output[index] = False
    return output


def _keep_largest_component(foreground: list[bool], width: int, height: int) -> list[bool]:
    largest: list[int] = []
    for component in _components(foreground, width, height, target=True):
        if len(component) > len(largest):
            largest = component

    keep = set(largest)
    return [index in keep for index in range(width * height)]


def _fill_small_holes(
    foreground: list[bool],
    width: int,
    height: int,
    max_size: int,
) -> tuple[list[bool], set[int]]:
    output = foreground.copy()
    filled: set[int] = set()
    for component in _components(foreground, width, height, target=False):
        touches_edge = any(_is_edge(index, width, height) for index in component)
        if not touches_edge and len(component) <= max_size:
            for index in component:
                output[index] = True
                filled.add(index)
    return output, filled


def _components(
    values: list[bool],
    width: int,
    height: int,
    target: bool,
) -> list[list[int]]:
    visited = [False] * len(values)
    components = []

    for start, value in enumerate(values):
        if visited[start] or value is not target:
            continue

        component = []
        queue = deque([start])
        visited[start] = True
        while queue:
            index = queue.popleft()
            component.append(index)
            for neighbor in _neighbors(index, width, height):
                if not visited[neighbor] and values[neighbor] is target:
                    visited[neighbor] = True
                    queue.append(neighbor)
        components.append(component)

    return components


def _neighbors(index: int, width: int, height: int):
    x = index % width
    y = index // width
    if x > 0:
        yield index - 1
    if x + 1 < width:
        yield index + 1
    if y > 0:
        yield index - width
    if y + 1 < height:
        yield index + width


def _is_edge(index: int, width: int, height: int) -> bool:
    x = index % width
    y = index // width
    return x == 0 or y == 0 or x == width - 1 or y == height - 1
