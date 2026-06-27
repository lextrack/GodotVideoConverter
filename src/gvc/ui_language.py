from __future__ import annotations

from gvc.ui_panels import QUALITY_OPTIONS


def apply_language(win) -> None:
    win.setWindowTitle(win._tr("window_title"))
    win.btn_add.setText(win._tr("add_files"))
    win.btn_remove.setText(win._tr("remove_selected"))
    win.btn_clear.setText(win._tr("clear"))
    win.output_label.setText(win._tr("output"))
    win.btn_output_change.setText(win._tr("change_output"))
    win.btn_output_open.setText(win._tr("open_output"))
    win.language_label.setText(win._tr("language"))
    win.btn_about.setText(win._tr("about"))
    win.engine_profile_label.setText(win._tr("engine_profile"))
    win.format_label.setText(win._tr("format"))
    win.quality_label.setText(win._tr("quality"))
    reload_quality_options(win)
    win.resolution_label.setText(win._tr("resolution"))
    win.resolution.setItemText(0, win._tr("keep_original"))
    if win.resolution.currentText() in win._all_translations("keep_original"):
        win.resolution.setCurrentText(win._tr("keep_original"))
    win.fps_label.setText(win._tr("fps"))
    win.keep_audio.setText(win._tr("keep_audio"))
    win.ogv_mode_label.setText(win._tr("ogv_mode"))
    win.frames_label.setText(win._tr("frames"))
    win.mode_label.setText(win._tr("mode"))
    win.atlas_resolution_label.setText(win._tr("atlas_frame_size"))
    win.rec_group.setTitle(win._tr("rec_title"))
    win.btn_cancel.setText(win._tr("cancel"))
    win.tabs.setTabText(0, win._tr("tab_convert"))
    win.tabs.setTabText(1, win._tr("tab_atlas"))
    win._reload_ogv_mode_options(win.engine_profile.currentText(), win._ogv_mode_value())
    win._reload_atlas_mode_options(win._atlas_mode_value())
    win._reload_atlas_resolution_options(win._atlas_resolution_value())
    win._update_action_button()
    win._refresh_status_label()
    win._refresh_experience_panels()


def reload_quality_options(win) -> None:
    current = win._quality_value()
    win.quality.blockSignals(True)
    win.quality.clear()
    for quality in QUALITY_OPTIONS:
        win.quality.addItem(win._tr(f"quality_{quality}"), quality)
    idx = win.quality.findData(current)
    if idx < 0:
        idx = win.quality.findData("optimized")
    win.quality.setCurrentIndex(idx if idx >= 0 else 0)
    win.quality.blockSignals(False)
