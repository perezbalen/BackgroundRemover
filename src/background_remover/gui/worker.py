"""Qt worker objects for background processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from background_remover.aseprite import flatten_frames, read_aseprite, write_flattened_aseprite
from background_remover.gui.input_loader import LoadedInput
from background_remover.gui.processing_options import GuiProcessingOptions
from background_remover.processing import (
    AsepriteProcessingSettings,
    ProgressEvent,
    StillImageProcessingSettings,
    prepare_output_file,
    process_aseprite,
    process_still_image,
    require_input_file,
    validate_aseprite_extension,
)

from PySide6.QtCore import QObject, Signal, Slot


class GuiCancellationToken:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


class ProcessingWorker(QObject):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        loaded_input: LoadedInput,
        output_path: Path,
        model_name: str,
        options: GuiProcessingOptions,
        overwrite: bool,
    ) -> None:
        super().__init__()
        self.loaded_input = loaded_input
        self.output_path = output_path
        self.model_name = model_name
        self.options = options
        self.overwrite = overwrite
        self.cancellation_token = GuiCancellationToken()

    def cancel(self) -> None:
        self.cancellation_token.cancel()

    @Slot()
    def run(self) -> None:
        try:
            metadata = self.loaded_input.metadata
            if metadata.input_type == "aseprite":
                result = process_aseprite(
                    AsepriteProcessingSettings(
                        input_path=metadata.path,
                        output_path=self.output_path,
                        model_name=self.model_name,
                        frame_output_dir=self.options.frame_output_dir,
                        mask_output_dir=self.options.mask_output_dir,
                        ai_mask_output_dir=self.options.ai_mask_output_dir,
                        color_key_mask_output_dir=self.options.color_key_mask_output_dir,
                        model_cache_dir=self.options.model_cache_dir,
                        cleanup_options=self.options.cleanup_options,
                        color_key_options=self.options.color_key_options,
                        report_output_path=self.options.report_output_path,
                        contact_sheet_output_path=self.options.contact_sheet_output_path,
                        preview_output_path=self.options.preview_output_path,
                        area_jump_threshold=self.options.area_jump_threshold,
                        bbox_jump_threshold=self.options.bbox_jump_threshold,
                        overwrite=self.overwrite,
                    ),
                    progress=self._emit_progress,
                    cancellation_token=self.cancellation_token,
                )
            else:
                result = process_still_image(
                    StillImageProcessingSettings(
                        input_path=metadata.path,
                        output_path=self.output_path,
                        model_name=self.model_name,
                        mask_output_path=self.options.still_mask_output_path,
                        model_cache_dir=self.options.model_cache_dir,
                        cleanup_options=self.options.cleanup_options,
                        overwrite=self.overwrite,
                    ),
                    progress=self._emit_progress,
                )
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    def _emit_progress(self, event: ProgressEvent) -> None:
        self.progress.emit(event)


@dataclass(frozen=True)
class BenchmarkModelResult:
    model_name: str
    seconds: float
    output_path: Path
    mask_path: Path


class RebuildNoopWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, input_path: Path, output_path: Path, overwrite: bool) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.overwrite = overwrite

    @Slot()
    def run(self) -> None:
        try:
            require_input_file(self.input_path, "Aseprite input")
            validate_aseprite_extension(self.input_path)
            prepare_output_file(
                self.output_path,
                overwrite=self.overwrite,
                label="rebuilt .aseprite",
            )
            sprite = read_aseprite(self.input_path)
            frames = flatten_frames(sprite)
            durations = [frame.duration_ms for frame in sprite.frames]
            write_flattened_aseprite(
                str(self.output_path),
                width=sprite.width,
                height=sprite.height,
                frame_pixels=frames,
                durations_ms=durations,
                tags=sprite.tags,
            )
            self.completed.emit(self.output_path)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class BenchmarkWorker(QObject):
    progress = Signal(str, int, int)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        model_names: list[str],
        model_cache_dir: Path,
        overwrite: bool,
    ) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.model_names = model_names
        self.model_cache_dir = model_cache_dir
        self.overwrite = overwrite

    @Slot()
    def run(self) -> None:
        try:
            from PIL import Image

            from background_remover.background import RembgBackgroundRemover

            require_input_file(self.input_path, "image input")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for model_name in self.model_names:
                prepare_output_file(
                    self.output_dir / f"{model_name}.png",
                    overwrite=self.overwrite,
                    label=f"{model_name} output image",
                )
                prepare_output_file(
                    self.output_dir / f"{model_name}.mask.png",
                    overwrite=self.overwrite,
                    label=f"{model_name} mask output",
                )

            with Image.open(self.input_path) as image:
                source = image.copy()

            results: list[BenchmarkModelResult] = []
            total = len(self.model_names)
            for index, model_name in enumerate(self.model_names, start=1):
                self.progress.emit(model_name, index, total)
                remover = RembgBackgroundRemover(
                    model_name,
                    model_cache_dir=str(self.model_cache_dir),
                )
                result = remover.remove(source)
                output_path = self.output_dir / f"{model_name}.png"
                mask_path = self.output_dir / f"{model_name}.mask.png"
                result.image.save(output_path)
                result.mask.save(mask_path)
                results.append(
                    BenchmarkModelResult(
                        model_name=model_name,
                        seconds=result.elapsed_seconds,
                        output_path=output_path,
                        mask_path=mask_path,
                    )
                )
            self.completed.emit(results)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
