"""Reusable processing service for CLI and GUI callers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Protocol

from background_remover.aseprite import (
    flatten_frames,
    read_aseprite,
    write_flattened_aseprite,
)
from background_remover.background import SUPPORTED_MODELS, BackgroundRemovalError, RemovalResult
from background_remover.color_key import (
    ColorKeyOptions,
    apply_color_key_assist,
    describe_color_key_options,
)
from background_remover.mask_cleanup import MaskCleanupOptions, apply_alpha_mask, apply_mask_cleanup
from background_remover.reporting import (
    build_processing_report,
    write_contact_sheet,
    write_gif_preview,
    write_processing_report,
)

DEFAULT_MODEL = "bria-rmbg"
DEFAULT_MODEL_CACHE_DIR = ".cache/rembg-models"
LAYER_POLICY = "flattened processed layer"
OUTPUT_LAYER_NAME = "Flattened"
METADATA_POLICY = {
    "canvas_size": "preserved",
    "frame_order": "preserved",
    "frame_count": "preserved",
    "frame_duration": "preserved",
    "animation_tags": "preserved",
    "slices": "not preserved",
    "layer_names": "not preserved; output uses a single Flattened layer",
}


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool:
        """Return true when processing should stop before the next frame."""


class BackgroundRemover(Protocol):
    def remove(self, image) -> RemovalResult:
        """Remove the background from one image."""


ProgressCallback = Callable[["ProgressEvent"], None]
RemoverFactory = Callable[[str, str | None], BackgroundRemover]


@dataclass(frozen=True)
class StillImageProcessingSettings:
    input_path: Path
    output_path: Path
    model_name: str = DEFAULT_MODEL
    mask_output_path: Path | None = None
    model_cache_dir: Path = field(default_factory=lambda: Path(DEFAULT_MODEL_CACHE_DIR))
    cleanup_options: MaskCleanupOptions = field(default_factory=MaskCleanupOptions)
    overwrite: bool = False


@dataclass(frozen=True)
class AsepriteProcessingSettings:
    input_path: Path
    output_path: Path
    model_name: str = DEFAULT_MODEL
    frame_output_dir: Path | None = None
    mask_output_dir: Path | None = None
    ai_mask_output_dir: Path | None = None
    color_key_mask_output_dir: Path | None = None
    model_cache_dir: Path = field(default_factory=lambda: Path(DEFAULT_MODEL_CACHE_DIR))
    cleanup_options: MaskCleanupOptions = field(default_factory=MaskCleanupOptions)
    color_key_options: ColorKeyOptions = field(default_factory=ColorKeyOptions)
    report_output_path: Path | None = None
    contact_sheet_output_path: Path | None = None
    preview_output_path: Path | None = None
    area_jump_threshold: float = 0.25
    bbox_jump_threshold: float = 32.0
    overwrite: bool = False


@dataclass(frozen=True)
class AsepriteDryRunPlan:
    input_path: Path
    output_path: Path
    width: int
    height: int
    frame_count: int
    durations_ms: list[int]
    tags: list[object]
    model_name: str
    model_cache_dir: Path
    cleanup_description: str
    color_key_description: str
    layer_policy: str
    metadata_policy: Mapping[str, str]


@dataclass(frozen=True)
class ProcessingTimings:
    processing_seconds: float
    total_seconds: float
    average_frame_seconds: float = 0.0


@dataclass(frozen=True)
class ProcessingArtifacts:
    output_path: Path
    mask_output_path: Path | None = None
    frame_output_dir: Path | None = None
    mask_output_dir: Path | None = None
    ai_mask_output_dir: Path | None = None
    color_key_mask_output_dir: Path | None = None
    report_output_path: Path | None = None
    contact_sheet_output_path: Path | None = None
    preview_output_path: Path | None = None


@dataclass(frozen=True)
class StillImageProcessingResult:
    artifacts: ProcessingArtifacts
    timings: ProcessingTimings
    model_name: str
    model_cache_dir: Path
    cleanup_description: str


@dataclass(frozen=True)
class AsepriteProcessingResult:
    artifacts: ProcessingArtifacts
    warnings: list[dict]
    timings: ProcessingTimings
    model_name: str
    model_cache_dir: Path
    cleanup_description: str
    color_key_description: str
    layer_policy: str
    metadata_policy: Mapping[str, str]
    frame_count: int
    width: int
    height: int
    report: dict


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    frame_index: int | None = None
    frame_count: int | None = None
    elapsed_seconds: float = 0.0
    message: str = ""


def require_input_file(path: str | Path, label: str) -> Path:
    input_path = Path(path)
    if not input_path.exists():
        raise BackgroundRemovalError(f"Missing {label}: {input_path}")
    if not input_path.is_file():
        raise BackgroundRemovalError(f"{label} is not a file: {input_path}")
    return input_path


def validate_aseprite_extension(path: str | Path) -> Path:
    input_path = Path(path)
    if input_path.suffix.lower() != ".aseprite":
        raise BackgroundRemovalError(f"Unsupported input extension for .aseprite command: {input_path}")
    return input_path


def validate_model_name(model_name: str) -> None:
    if model_name not in SUPPORTED_MODELS:
        supported = ", ".join(SUPPORTED_MODELS)
        raise BackgroundRemovalError(f"Unsupported model '{model_name}'. Supported: {supported}")


def prepare_output_file(path: str | Path, *, overwrite: bool, label: str) -> Path:
    output = Path(path)
    if output.exists() and not overwrite:
        raise BackgroundRemovalError(f"{label} already exists: {output} (use --overwrite to replace it)")
    if output.parent and str(output.parent) != ".":
        output.parent.mkdir(parents=True, exist_ok=True)
    return output


def describe_cleanup(options: MaskCleanupOptions) -> str:
    if not options.enabled:
        return "disabled"
    threshold = "none" if options.alpha_threshold is None else str(options.alpha_threshold)
    return (
        f"alpha_threshold={threshold}, "
        f"min_artifact_size={options.min_artifact_size}, "
        f"fill_hole_size={options.fill_hole_size}, "
        f"keep_largest_component={options.keep_largest_component}, "
        f"feather_radius={options.feather_radius:g}"
    )


def build_aseprite_dry_run_plan(settings: AsepriteProcessingSettings) -> AsepriteDryRunPlan:
    validate_model_name(settings.model_name)
    input_path = validate_aseprite_extension(require_input_file(settings.input_path, "Aseprite input"))
    sprite = read_aseprite(input_path)
    return AsepriteDryRunPlan(
        input_path=input_path,
        output_path=settings.output_path,
        width=sprite.width,
        height=sprite.height,
        frame_count=sprite.frame_count,
        durations_ms=[frame.duration_ms for frame in sprite.frames],
        tags=list(sprite.tags),
        model_name=settings.model_name,
        model_cache_dir=settings.model_cache_dir,
        cleanup_description=describe_cleanup(settings.cleanup_options),
        color_key_description=describe_color_key_options(settings.color_key_options),
        layer_policy=LAYER_POLICY,
        metadata_policy=METADATA_POLICY,
    )


def process_still_image(
    settings: StillImageProcessingSettings,
    *,
    remover_factory: RemoverFactory | None = None,
    progress: ProgressCallback | None = None,
) -> StillImageProcessingResult:
    try:
        from PIL import Image
    except ImportError as error:
        raise BackgroundRemovalError(
            "Missing Pillow dependency. Run: " 'python3 -m pip install -e ".[dev]"'
        ) from error

    validate_model_name(settings.model_name)
    input_path = require_input_file(settings.input_path, "image input")
    output_path = prepare_output_file(
        settings.output_path,
        overwrite=settings.overwrite,
        label="output image",
    )
    mask_output_path = None
    if settings.mask_output_path:
        mask_output_path = prepare_output_file(
            settings.mask_output_path,
            overwrite=settings.overwrite,
            label="mask output",
        )

    emit = progress or _ignore_progress
    started = time.perf_counter()
    emit(ProgressEvent(stage="loading", message=f"Loading {input_path}"))

    with Image.open(input_path) as image:
        source = image.copy()

    emit(ProgressEvent(stage="model", message=f"Loading model {settings.model_name}"))
    remover = _build_remover(remover_factory, settings.model_name, settings.model_cache_dir)
    emit(ProgressEvent(stage="processing", frame_index=0, frame_count=1))
    result = remover.remove(source)

    try:
        cleaned_mask = apply_mask_cleanup(result.mask, settings.cleanup_options)
    except ValueError as error:
        raise BackgroundRemovalError(str(error)) from error

    if not settings.cleanup_options.enabled:
        processed = result.image.convert("RGBA")
        mask = result.mask.convert("L")
    else:
        processed = apply_alpha_mask(result.image, cleaned_mask)
        mask = cleaned_mask

    processed.save(output_path)
    if mask_output_path:
        mask.save(mask_output_path)

    total_elapsed = time.perf_counter() - started
    emit(
        ProgressEvent(
            stage="completed",
            frame_index=1,
            frame_count=1,
            elapsed_seconds=total_elapsed,
        )
    )

    return StillImageProcessingResult(
        artifacts=ProcessingArtifacts(
            output_path=output_path,
            mask_output_path=mask_output_path,
        ),
        timings=ProcessingTimings(
            processing_seconds=result.elapsed_seconds,
            total_seconds=total_elapsed,
            average_frame_seconds=result.elapsed_seconds,
        ),
        model_name=settings.model_name,
        model_cache_dir=settings.model_cache_dir,
        cleanup_description=describe_cleanup(settings.cleanup_options),
    )


def process_aseprite(
    settings: AsepriteProcessingSettings,
    *,
    remover_factory: RemoverFactory | None = None,
    progress: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> AsepriteProcessingResult:
    try:
        from PIL import Image
    except ImportError as error:
        raise BackgroundRemovalError(
            "Missing Pillow dependency. Run: " 'python3 -m pip install -e ".[dev]"'
        ) from error

    validate_model_name(settings.model_name)
    input_path = validate_aseprite_extension(require_input_file(settings.input_path, "Aseprite input"))
    output_path = prepare_output_file(
        settings.output_path,
        overwrite=settings.overwrite,
        label="output .aseprite",
    )
    report_output_path = _prepare_optional_file(
        settings.report_output_path,
        overwrite=settings.overwrite,
        label="JSON report",
    )
    contact_sheet_output_path = _prepare_optional_file(
        settings.contact_sheet_output_path,
        overwrite=settings.overwrite,
        label="contact sheet",
    )
    preview_output_path = _prepare_optional_file(
        settings.preview_output_path,
        overwrite=settings.overwrite,
        label="animated preview",
    )

    frame_output = _prepare_optional_dir(settings.frame_output_dir)
    mask_output = _prepare_optional_dir(settings.mask_output_dir)
    ai_mask_output = _prepare_optional_dir(settings.ai_mask_output_dir)
    color_key_mask_output = _prepare_optional_dir(settings.color_key_mask_output_dir)

    emit = progress or _ignore_progress
    total_started = time.perf_counter()
    emit(ProgressEvent(stage="loading", message=f"Loading {input_path}"))
    sprite = read_aseprite(input_path)
    source_frames = flatten_frames(sprite)
    durations = [frame.duration_ms for frame in sprite.frames]
    cleanup_description = describe_cleanup(settings.cleanup_options)
    color_key_description = describe_color_key_options(settings.color_key_options)

    emit(ProgressEvent(stage="model", message=f"Loading model {settings.model_name}"))
    remover = _build_remover(remover_factory, settings.model_name, settings.model_cache_dir)

    processed_frames: list[bytes] = []
    original_images = []
    mask_images = []
    processed_images = []
    processing_elapsed = 0.0
    frame_count = len(source_frames)

    for index, pixels in enumerate(source_frames):
        if cancellation_token and cancellation_token.is_cancelled():
            raise BackgroundRemovalError("Processing cancelled")

        emit(
            ProgressEvent(
                stage="processing",
                frame_index=index,
                frame_count=frame_count,
                elapsed_seconds=time.perf_counter() - total_started,
            )
        )
        image = Image.frombytes("RGBA", (sprite.width, sprite.height), pixels)
        result = remover.remove(image)
        if result.image.size != (sprite.width, sprite.height):
            raise BackgroundRemovalError(
                f"Model returned frame {index + 1} at {result.image.width}x{result.image.height}; "
                f"expected {sprite.width}x{sprite.height}"
            )

        try:
            cleaned_mask = apply_mask_cleanup(result.mask, settings.cleanup_options)
            color_key_result = apply_color_key_assist(
                image,
                cleaned_mask,
                settings.color_key_options,
            )
        except ValueError as error:
            raise BackgroundRemovalError(str(error)) from error

        final_mask = color_key_result.combined_mask if color_key_result else cleaned_mask
        if not settings.cleanup_options.enabled and color_key_result is None:
            processed = result.image.convert("RGBA")
        else:
            processed = apply_alpha_mask(result.image, final_mask)
        processed_frames.append(processed.tobytes())
        original_images.append(image.copy())
        mask_images.append(final_mask.copy())
        processed_images.append(processed.copy())
        processing_elapsed += result.elapsed_seconds

        frame_name = f"frame-{index:04d}.png"
        if frame_output:
            processed.save(frame_output / frame_name)
        if mask_output:
            final_mask.save(mask_output / frame_name)
        if ai_mask_output:
            cleaned_mask.save(ai_mask_output / frame_name)
        if color_key_mask_output and color_key_result:
            color_key_result.color_key_mask.save(color_key_mask_output / frame_name)

        emit(
            ProgressEvent(
                stage="frame_completed",
                frame_index=index + 1,
                frame_count=frame_count,
                elapsed_seconds=result.elapsed_seconds,
            )
        )

    write_flattened_aseprite(
        str(output_path),
        width=sprite.width,
        height=sprite.height,
        frame_pixels=processed_frames,
        durations_ms=durations,
        tags=sprite.tags,
        layer_name=OUTPUT_LAYER_NAME,
    )

    total_elapsed = time.perf_counter() - total_started
    average_elapsed = processing_elapsed / frame_count if frame_count else 0.0
    report = build_processing_report(
        input_path=str(input_path),
        output_path=str(output_path),
        model_name=settings.model_name,
        cleanup=cleanup_description,
        color_key=color_key_description,
        layer_policy=LAYER_POLICY,
        metadata_policy=METADATA_POLICY,
        width=sprite.width,
        height=sprite.height,
        durations_ms=durations,
        masks=mask_images,
        processing_seconds=processing_elapsed,
        total_seconds=total_elapsed,
        area_jump_threshold=settings.area_jump_threshold,
        bbox_jump_threshold=settings.bbox_jump_threshold,
    )

    if report_output_path:
        write_processing_report(report_output_path, report)
    if contact_sheet_output_path:
        write_contact_sheet(contact_sheet_output_path, original_images, mask_images, processed_images)
    if preview_output_path:
        write_gif_preview(preview_output_path, processed_images, durations)

    emit(
        ProgressEvent(
            stage="completed",
            frame_index=frame_count,
            frame_count=frame_count,
            elapsed_seconds=total_elapsed,
        )
    )

    return AsepriteProcessingResult(
        artifacts=ProcessingArtifacts(
            output_path=output_path,
            frame_output_dir=frame_output,
            mask_output_dir=mask_output,
            ai_mask_output_dir=ai_mask_output,
            color_key_mask_output_dir=color_key_mask_output,
            report_output_path=report_output_path,
            contact_sheet_output_path=contact_sheet_output_path,
            preview_output_path=preview_output_path,
        ),
        warnings=list(report["warnings"]),
        timings=ProcessingTimings(
            processing_seconds=processing_elapsed,
            total_seconds=total_elapsed,
            average_frame_seconds=average_elapsed,
        ),
        model_name=settings.model_name,
        model_cache_dir=settings.model_cache_dir,
        cleanup_description=cleanup_description,
        color_key_description=color_key_description,
        layer_policy=LAYER_POLICY,
        metadata_policy=METADATA_POLICY,
        frame_count=frame_count,
        width=sprite.width,
        height=sprite.height,
        report=report,
    )


def _build_remover(
    remover_factory: RemoverFactory | None,
    model_name: str,
    model_cache_dir: Path,
) -> BackgroundRemover:
    if remover_factory:
        return remover_factory(model_name, str(model_cache_dir))

    from background_remover.background import RembgBackgroundRemover

    return RembgBackgroundRemover(model_name, model_cache_dir=str(model_cache_dir))


def _prepare_optional_file(path: Path | None, *, overwrite: bool, label: str) -> Path | None:
    if path is None:
        return None
    return prepare_output_file(path, overwrite=overwrite, label=label)


def _prepare_optional_dir(path: Path | None) -> Path | None:
    if path is None:
        return None
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ignore_progress(event: ProgressEvent) -> None:
    return None
