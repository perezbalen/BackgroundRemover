"""Qt worker objects for background processing."""

from __future__ import annotations

from pathlib import Path

from background_remover.gui.input_loader import LoadedInput
from background_remover.gui.processing_options import GuiProcessingOptions
from background_remover.processing import (
    AsepriteProcessingSettings,
    ProgressEvent,
    StillImageProcessingSettings,
    process_aseprite,
    process_still_image,
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
