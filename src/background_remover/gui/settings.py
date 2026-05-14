"""Persistent GUI settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from background_remover.processing import DEFAULT_MODEL, DEFAULT_MODEL_CACHE_DIR


@dataclass
class GuiSettings:
    recent_folders: list[Path] = field(default_factory=list)
    model_name: str = DEFAULT_MODEL
    model_cache_dir: Path = field(default_factory=lambda: Path(DEFAULT_MODEL_CACHE_DIR))

    @classmethod
    def load(cls, qsettings) -> "GuiSettings":
        recent = qsettings.value("recentFolders", [], type=list)
        return cls(
            recent_folders=[Path(folder) for folder in recent],
            model_name=qsettings.value("modelName", DEFAULT_MODEL, type=str),
            model_cache_dir=Path(
                qsettings.value("modelCacheDir", DEFAULT_MODEL_CACHE_DIR, type=str)
            ),
        )

    def save(self, qsettings) -> None:
        qsettings.setValue("recentFolders", [str(folder) for folder in self.recent_folders])
        qsettings.setValue("modelName", self.model_name)
        qsettings.setValue("modelCacheDir", str(self.model_cache_dir))
