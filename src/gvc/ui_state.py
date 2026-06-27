from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QComboBox

from gvc.settings import AppSettings, load_settings, save_settings


def apply_saved_settings(win) -> None:
    win._loading_settings = True
    try:
        apply_settings(win, load_settings())
    finally:
        win._loading_settings = False


def apply_settings(win, settings: AppSettings) -> None:
    _set_combo_value(win.language, settings.selected_language, "English")
    win.output.setText(settings.output_folder or str(Path.cwd() / "output"))
    _set_combo_value(win.engine_profile, settings.selected_engine_profile, "Godot")
    _set_combo_value(win.format, settings.selected_format, "ogv")
    _set_combo_value(win.quality, settings.selected_quality, "optimized")
    _set_editable_combo_value(win.resolution, settings.selected_resolution, "Keep original")
    win.fps.setValue(coerce_video_fps(settings.fps))
    win.keep_audio.setChecked(settings.keep_audio)
    win._reload_ogv_mode_options(win.engine_profile.currentText(), settings.selected_ogv_mode)
    win.atlas_fps.setValue(max(1, min(30, settings.atlas_fps or 5)))
    win._reload_atlas_mode_options(settings.selected_atlas_mode)
    win._reload_atlas_resolution_options(settings.selected_atlas_resolution)


def collect_settings(win) -> AppSettings:
    return AppSettings(
        selected_language=win.language.currentText(),
        output_folder=win.output.text().strip() or "output",
        selected_engine_profile=win.engine_profile.currentText(),
        selected_format=win.format.currentText(),
        selected_resolution=win.resolution.currentText().strip() or "Keep original",
        selected_quality=win.quality.currentText(),
        selected_ogv_mode=win._ogv_mode_value(),
        keep_audio=win.keep_audio.isChecked(),
        fps=f"{win.fps.value():g}",
        atlas_fps=win.atlas_fps.value(),
        selected_atlas_mode=win._atlas_mode_value(),
        selected_atlas_resolution=win._atlas_resolution_value(),
    )


def save_window_settings(win) -> None:
    if win._loading_settings:
        return
    try:
        save_settings(collect_settings(win))
    except OSError as exc:
        print(f"Warning: failed to save settings: {exc}", file=sys.stderr)


def coerce_video_fps(value: str | float | int | None) -> float:
    try:
        fps = float(value) if value is not None else 30.0
    except (TypeError, ValueError):
        fps = 30.0
    return max(1.0, min(60.0, fps))


def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
    idx = combo.findText(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return
    fallback_idx = combo.findText(fallback)
    if fallback_idx >= 0:
        combo.setCurrentIndex(fallback_idx)


def _set_editable_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
    chosen = (value or "").strip() or fallback
    idx = combo.findText(chosen)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return
    combo.setCurrentText(chosen)
