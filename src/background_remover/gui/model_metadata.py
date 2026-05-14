"""Model metadata shown by the GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from background_remover.background import SUPPORTED_MODELS


@dataclass(frozen=True)
class ModelMetadata:
    best_use: str
    cpu_cost: str
    license_note: str = ""


MODEL_METADATA = {
    "isnet-anime": ModelMetadata("stylized and anime-like sprites", "medium"),
    "isnet-general-use": ModelMetadata("general objects", "medium"),
    "bria-rmbg": ModelMetadata(
        "high-quality general removal",
        "slow",
        "Review the upstream BRIA model license before commercial use.",
    ),
    "birefnet-general-lite": ModelMetadata("general objects with lighter BiRefNet cost", "slow"),
    "birefnet-general": ModelMetadata("high-quality general removal", "very slow"),
    "birefnet-portrait": ModelMetadata("portrait and human subjects", "very slow"),
    "birefnet-dis": ModelMetadata("dichotomous image segmentation", "very slow"),
    "birefnet-hrsod": ModelMetadata("high-resolution salient objects", "very slow"),
    "birefnet-cod": ModelMetadata("camouflaged objects", "very slow"),
    "birefnet-massive": ModelMetadata("maximum-quality BiRefNet candidate", "very slow"),
    "u2net": ModelMetadata("general fallback", "medium"),
    "u2netp": ModelMetadata("fast draft fallback", "fast"),
    "u2net_human_seg": ModelMetadata("human subjects", "medium"),
    "silueta": ModelMetadata("fast draft fallback", "fast"),
}


def describe_model(model_name: str, cache_dir: Path) -> str:
    metadata = MODEL_METADATA.get(model_name, ModelMetadata("general removal", "unknown"))
    cache_status = "cached" if is_model_cached(model_name, cache_dir) else "not cached"
    lines = [
        f"Best for: {metadata.best_use}",
        f"Expected CPU cost: {metadata.cpu_cost}",
        f"Cache: {cache_status}",
    ]
    if metadata.license_note:
        lines.append(metadata.license_note)
    return "\n".join(lines)


def is_model_cached(model_name: str, cache_dir: Path) -> bool:
    if not cache_dir.exists():
        return False
    normalized = model_name.replace("-", "").replace("_", "").lower()
    for path in cache_dir.rglob("*"):
        name = path.name.replace("-", "").replace("_", "").lower()
        if normalized in name:
            return True
    return False


def supported_model_names() -> tuple[str, ...]:
    return SUPPORTED_MODELS
