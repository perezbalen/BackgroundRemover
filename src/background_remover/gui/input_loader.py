"""Input preview loading for still images and Aseprite files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from background_remover.aseprite import flatten_frames, read_aseprite

SUPPORTED_STILL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
SUPPORTED_ASEPRITE_EXTENSION = ".aseprite"
SUPPORTED_INPUT_EXTENSIONS = SUPPORTED_STILL_EXTENSIONS | {SUPPORTED_ASEPRITE_EXTENSION}


@dataclass(frozen=True)
class PreviewFrame:
    width: int
    height: int
    rgba: bytes
    duration_ms: int = 100


@dataclass(frozen=True)
class InputMetadata:
    path: Path
    input_type: str
    width: int
    height: int
    frame_count: int
    durations_ms: list[int] = field(default_factory=list)
    layer_count: int = 0
    tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LoadedInput:
    metadata: InputMetadata
    frames: list[PreviewFrame]


def is_supported_input_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def split_supported_paths(paths: list[Path]) -> tuple[Path | None, list[Path]]:
    supported = [path for path in paths if is_supported_input_path(path)]
    selected = supported[0] if supported else None
    skipped = [path for path in paths if path != selected]
    return selected, skipped


def load_input(path: str | Path) -> LoadedInput:
    input_path = Path(path)
    suffix = input_path.suffix.lower()
    if suffix == SUPPORTED_ASEPRITE_EXTENSION:
        return load_aseprite_input(input_path)
    if suffix in SUPPORTED_STILL_EXTENSIONS:
        return load_still_input(input_path)
    supported = ", ".join(sorted(SUPPORTED_INPUT_EXTENSIONS))
    raise ValueError(f"Unsupported input extension '{suffix}'. Supported: {supported}")


def load_still_input(path: str | Path) -> LoadedInput:
    input_path = Path(path)
    with Image.open(input_path) as image:
        rgba = image.convert("RGBA")
        frame = PreviewFrame(
            width=rgba.width,
            height=rgba.height,
            rgba=rgba.tobytes(),
            duration_ms=100,
        )
    return LoadedInput(
        metadata=InputMetadata(
            path=input_path,
            input_type="image",
            width=frame.width,
            height=frame.height,
            frame_count=1,
            durations_ms=[frame.duration_ms],
        ),
        frames=[frame],
    )


def load_aseprite_input(path: str | Path) -> LoadedInput:
    input_path = Path(path)
    sprite = read_aseprite(str(input_path))
    flattened = flatten_frames(sprite)
    durations = [frame.duration_ms for frame in sprite.frames]
    frames = [
        PreviewFrame(
            width=sprite.width,
            height=sprite.height,
            rgba=pixels,
            duration_ms=durations[index],
        )
        for index, pixels in enumerate(flattened)
    ]
    warnings = [
        "Slices are not preserved by the current processing pipeline.",
        "Layer names are flattened into a single output layer after processing.",
    ]
    return LoadedInput(
        metadata=InputMetadata(
            path=input_path,
            input_type="aseprite",
            width=sprite.width,
            height=sprite.height,
            frame_count=sprite.frame_count,
            durations_ms=durations,
            layer_count=len(sprite.layers),
            tags=[f"{tag.name}: {tag.from_frame}-{tag.to_frame}" for tag in sprite.tags],
            warnings=warnings,
        ),
        frames=frames,
    )
