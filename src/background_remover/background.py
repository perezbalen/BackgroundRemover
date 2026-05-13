"""Background-removal model wrappers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING

from background_remover.mask_cleanup import (
    MaskCleanupOptions,
    apply_alpha_mask,
    apply_mask_cleanup,
)

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

SUPPORTED_MODELS = (
    "isnet-anime",
    "isnet-general-use",
    "bria-rmbg",
    "birefnet-general-lite",
    "birefnet-general",
    "birefnet-portrait",
    "birefnet-dis",
    "birefnet-hrsod",
    "birefnet-cod",
    "birefnet-massive",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
)


class BackgroundRemovalError(RuntimeError):
    """Raised when background removal cannot be completed."""


@dataclass(frozen=True)
class RemovalResult:
    image: "PILImage"
    mask: "PILImage"
    elapsed_seconds: float


class RembgBackgroundRemover:
    """CPU-oriented rembg wrapper with one reusable model session."""

    def __init__(self, model_name: str, model_cache_dir: str | None = None):
        if model_name not in SUPPORTED_MODELS:
            supported = ", ".join(SUPPORTED_MODELS)
            raise BackgroundRemovalError(f"Unsupported model '{model_name}'. Supported: {supported}")

        try:
            from rembg import new_session
        except ImportError as error:
            raise BackgroundRemovalError(
                "Missing background-removal dependencies. Run: "
                'python3 -m pip install -e ".[dev]"'
            ) from error

        self.model_name = model_name
        self.model_cache_dir = Path(model_cache_dir or ".cache/rembg-models")
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ["U2NET_HOME"] = str(self.model_cache_dir.resolve())
        try:
            self.session = new_session(model_name, providers=["CPUExecutionProvider"])
        except Exception as error:
            raise BackgroundRemovalError(
                f"Failed to load or download model '{model_name}' in "
                f"{self.model_cache_dir}. Check network access or cached model files."
            ) from error

    def remove(self, image: "PILImage") -> RemovalResult:
        try:
            from PIL import Image
            from rembg import remove
        except ImportError as error:
            raise BackgroundRemovalError(
                "Missing background-removal dependencies. Run: "
                'python3 -m pip install -e ".[dev]"'
            ) from error

        input_image = image.convert("RGBA")
        started = time.perf_counter()
        output = remove(input_image, session=self.session)
        elapsed = time.perf_counter() - started

        if not isinstance(output, Image.Image):
            raise BackgroundRemovalError("rembg returned an unsupported image output type")

        rgba_output = output.convert("RGBA")
        return RemovalResult(
            image=rgba_output,
            mask=rgba_output.getchannel("A"),
            elapsed_seconds=elapsed,
        )


def remove_image_file(
    input_path: str,
    output_path: str,
    model_name: str,
    mask_output_path: str | None = None,
    model_cache_dir: str | None = None,
    cleanup_options: MaskCleanupOptions | None = None,
) -> RemovalResult:
    try:
        from PIL import Image
    except ImportError as error:
        raise BackgroundRemovalError(
            "Missing Pillow dependency. Run: " 'python3 -m pip install -e ".[dev]"'
        ) from error

    remover = RembgBackgroundRemover(model_name, model_cache_dir=model_cache_dir)
    with Image.open(input_path) as image:
        result = remover.remove(image)

    result = clean_removal_result(result, cleanup_options)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.image.save(output)

    if mask_output_path:
        mask_output = Path(mask_output_path)
        mask_output.parent.mkdir(parents=True, exist_ok=True)
        result.mask.save(mask_output)

    return result


def clean_removal_result(
    result: RemovalResult,
    cleanup_options: MaskCleanupOptions | None = None,
) -> RemovalResult:
    options = cleanup_options or MaskCleanupOptions()
    if not options.enabled:
        return RemovalResult(
            image=result.image.copy(),
            mask=result.mask.convert("L").copy(),
            elapsed_seconds=result.elapsed_seconds,
        )

    try:
        cleaned_mask = apply_mask_cleanup(result.mask, options)
    except ValueError as error:
        raise BackgroundRemovalError(str(error)) from error

    return RemovalResult(
        image=apply_alpha_mask(result.image, cleaned_mask),
        mask=cleaned_mask,
        elapsed_seconds=result.elapsed_seconds,
    )


def benchmark_image_file(
    input_path: str,
    output_dir: str,
    model_names: list[str],
    model_cache_dir: str | None = None,
) -> list[tuple[str, RemovalResult]]:
    try:
        from PIL import Image
    except ImportError as error:
        raise BackgroundRemovalError(
            "Missing Pillow dependency. Run: " 'python3 -m pip install -e ".[dev]"'
        ) from error

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    results: list[tuple[str, RemovalResult]] = []
    with Image.open(input_path) as image:
        source = image.copy()

    for model_name in model_names:
        remover = RembgBackgroundRemover(model_name, model_cache_dir=model_cache_dir)
        result = remover.remove(source)
        result.image.save(output / f"{model_name}.png")
        result.mask.save(output / f"{model_name}.mask.png")
        results.append((model_name, result))

    return results
