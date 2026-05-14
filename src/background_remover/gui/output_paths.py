"""Output path helpers for GUI processing."""

from __future__ import annotations

from pathlib import Path


def suggest_output_path(input_path: Path) -> Path:
    if input_path.suffix.lower() == ".aseprite":
        return input_path.with_name(f"{input_path.stem}.processed.aseprite")
    return input_path.with_name(f"{input_path.stem}.transparent.png")
