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


def _coerce_str(value, default: str) -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    return text or default


def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(value, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_settings(data: dict[str, object]) -> AppSettings:
    defaults = AppSettings()
    return AppSettings(
        selected_language=_coerce_str(data.get("selected_language"), defaults.selected_language),
        output_folder=_coerce_str(data.get("output_folder"), defaults.output_folder),
        selected_engine_profile=_coerce_str(data.get("selected_engine_profile"), defaults.selected_engine_profile),
        selected_format=_coerce_str(data.get("selected_format"), defaults.selected_format),
        selected_resolution=_coerce_str(data.get("selected_resolution"), defaults.selected_resolution),
        selected_quality=_coerce_str(data.get("selected_quality"), defaults.selected_quality),
        selected_ogv_mode=_coerce_str(data.get("selected_ogv_mode"), defaults.selected_ogv_mode),
        keep_audio=_coerce_bool(data.get("keep_audio"), defaults.keep_audio),
        fps=_coerce_str(data.get("fps"), defaults.fps),
        selected_audio_format=_coerce_str(data.get("selected_audio_format"), defaults.selected_audio_format),
        selected_audio_bitrate=_coerce_str(data.get("selected_audio_bitrate"), defaults.selected_audio_bitrate),
        selected_audio_sample_rate=_coerce_str(data.get("selected_audio_sample_rate"), defaults.selected_audio_sample_rate),
        selected_audio_channels=_coerce_str(data.get("selected_audio_channels"), defaults.selected_audio_channels),
        atlas_fps=_coerce_int(data.get("atlas_fps"), defaults.atlas_fps),
        selected_atlas_mode=_coerce_str(data.get("selected_atlas_mode"), defaults.selected_atlas_mode),
        selected_atlas_resolution=_coerce_str(data.get("selected_atlas_resolution"), defaults.selected_atlas_resolution),
        info_panel_visible=_coerce_bool(data.get("info_panel_visible"), defaults.info_panel_visible),
    )


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
    if not isinstance(data, dict):
        return AppSettings()
    return _coerce_settings(data)


def save_settings(settings: AppSettings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path
