from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from background_remover.background import BackgroundRemovalError, RemovalResult
from background_remover.mask_cleanup import MaskCleanupOptions
from background_remover.processing import (
    AsepriteProcessingSettings,
    ProgressEvent,
    StillImageProcessingSettings,
    build_aseprite_dry_run_plan,
    prepare_output_file,
    process_aseprite,
    process_still_image,
    require_input_file,
    validate_aseprite_extension,
)


class FakeRemover:
    def remove(self, image: Image.Image) -> RemovalResult:
        rgba = image.convert("RGBA")
        mask = Image.new("L", rgba.size, 255)
        rgba.putalpha(mask)
        return RemovalResult(image=rgba, mask=mask, elapsed_seconds=0.125)


class CancelImmediately:
    def is_cancelled(self) -> bool:
        return True


def fake_remover_factory(model_name: str, model_cache_dir: str | None) -> FakeRemover:
    assert model_name == "bria-rmbg"
    assert model_cache_dir is not None
    return FakeRemover()


def test_validation_helpers_reject_missing_input_and_existing_output(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    existing = tmp_path / "existing.png"
    existing.write_bytes(b"already here")

    with pytest.raises(BackgroundRemovalError, match="Missing image input"):
        require_input_file(missing, "image input")

    with pytest.raises(BackgroundRemovalError, match="already exists"):
        prepare_output_file(existing, overwrite=False, label="output image")


def test_validate_aseprite_extension_rejects_other_suffix() -> None:
    with pytest.raises(BackgroundRemovalError, match="Unsupported input extension"):
        validate_aseprite_extension("sprite.png")


def test_build_aseprite_dry_run_plan_reads_metadata() -> None:
    plan = build_aseprite_dry_run_plan(
        AsepriteProcessingSettings(
            input_path=Path("images/sprite.aseprite"),
            output_path=Path("output/sprite.processed.aseprite"),
        )
    )

    assert plan.frame_count > 0
    assert plan.width > 0
    assert plan.height > 0
    assert plan.model_name == "bria-rmbg"
    assert plan.layer_policy == "flattened processed layer"


def test_process_still_image_uses_typed_settings_and_returns_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGBA", (2, 2), (10, 20, 30, 255)).save(input_path)

    result = process_still_image(
        StillImageProcessingSettings(
            input_path=input_path,
            output_path=output_path,
            mask_output_path=mask_path,
            cleanup_options=MaskCleanupOptions(enabled=False),
        ),
        remover_factory=fake_remover_factory,
    )

    assert result.artifacts.output_path == output_path
    assert result.artifacts.mask_output_path == mask_path
    assert result.timings.processing_seconds == 0.125
    assert output_path.exists()
    assert mask_path.exists()


def test_process_aseprite_emits_progress_and_writes_artifacts(tmp_path: Path) -> None:
    output_path = tmp_path / "sprite.processed.aseprite"
    report_path = tmp_path / "report.json"
    events: list[ProgressEvent] = []

    result = process_aseprite(
        AsepriteProcessingSettings(
            input_path=Path("images/sprite.aseprite"),
            output_path=output_path,
            report_output_path=report_path,
        ),
        remover_factory=fake_remover_factory,
        progress=events.append,
    )

    assert result.artifacts.output_path == output_path
    assert result.artifacts.report_output_path == report_path
    assert result.frame_count > 0
    assert output_path.exists()
    assert report_path.exists()
    assert any(event.stage == "frame_completed" for event in events)
    assert events[-1].stage == "completed"


def test_process_aseprite_checks_cancellation_before_frame_work(tmp_path: Path) -> None:
    with pytest.raises(BackgroundRemovalError, match="Processing cancelled"):
        process_aseprite(
            AsepriteProcessingSettings(
                input_path=Path("images/sprite.aseprite"),
                output_path=tmp_path / "cancelled.aseprite",
            ),
            remover_factory=fake_remover_factory,
            cancellation_token=CancelImmediately(),
        )
