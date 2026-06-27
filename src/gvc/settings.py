from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    selected_language: str = "English"
    output_folder: str = "output"
    selected_engine_profile: str = "Godot"
    selected_format: str = "ogv"
    selected_resolution: str = "Keep original"
    selected_quality: str = "optimized"
    selected_ogv_mode: str = "Official Godot"
    keep_audio: bool = False
    fps: str = "30"
    selected_audio_format: str = "ogg"
    selected_audio_bitrate: str = "160k"
    selected_audio_sample_rate: str = "44100"
    selected_audio_channels: str = "stereo"
    atlas_fps: int = 5
    selected_atlas_mode: str = "grid"
    selected_atlas_resolution: str = "Medium"
    info_panel_visible: bool = True


def _config_dir() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if appdata:
            return Path(appdata) / "gvc"
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "gvc"
    return Path.home() / ".config" / "gvc"


def settings_path() -> Path:
    return _config_dir() / "settings.json"


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AppSettings()

    base = AppSettings()
    for key in data:
        if hasattr(base, key):
            setattr(base, key, data[key])
    return base


def save_settings(settings: AppSettings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path
