from __future__ import annotations

from pathlib import Path

from background_remover.cli import main


def test_list_models_marks_default(capsys) -> None:
    assert main(["--list-models"]) == 0

    output = capsys.readouterr().out
    assert "bria-rmbg (default)" in output


def test_process_dry_run_does_not_require_model(capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "sprite.processed.aseprite"

    assert main(["process", "images/sprite.aseprite", str(output_path), "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "Dry run: images/sprite.aseprite" in output
    assert f"Planned output: {output_path}" in output
    assert "Model: bria-rmbg" in output
    assert not output_path.exists()


def test_rebuild_noop_cli_writes_output(tmp_path: Path) -> None:
    output_path = tmp_path / "sprite.rebuilt.aseprite"

    assert main(["rebuild-noop", "images/sprite.aseprite", str(output_path)]) == 0

    assert output_path.exists()
