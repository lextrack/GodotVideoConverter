from __future__ import annotations

from gvc.convert import ogv_modes_for_profile


def set_busy(win, busy: bool) -> None:
    win.btn_action.setEnabled(not busy)
    win.files.setEnabled(not busy)
    win.btn_add.setEnabled(not busy)
    win.btn_remove.setEnabled(not busy)
    win.btn_clear.setEnabled(not busy)
    win.btn_toggle_info.setEnabled(not busy)
    win.output.setEnabled(not busy)
    win.btn_output_change.setEnabled(not busy)
    win.btn_output_open.setEnabled(True)
    win.btn_about.setEnabled(not busy)
    win.language.setEnabled(not busy)
    win.tabs.setEnabled(not busy)
    win.format.setEnabled(not busy)
    win.quality.setEnabled(not busy)
    win.resolution.setEnabled(not busy)
    win.fps.setEnabled(not busy)
    is_ogv = win.format.currentText().strip().lower() == "ogv"
    win.engine_profile_label.setEnabled(not busy and is_ogv)
    win.engine_profile.setEnabled(not busy and is_ogv)
    win.keep_audio.setEnabled(not busy)
    win.ogv_mode_label.setEnabled(not busy and is_ogv)
    win.ogv_mode.setEnabled(not busy and is_ogv)
    win.audio_format.setEnabled(not busy)
    win.audio_bitrate.setEnabled(not busy and win._audio_format_value() != "wav")
    win.audio_bitrate_label.setEnabled(not busy and win._audio_format_value() != "wav")
    win.audio_sample_rate.setEnabled(not busy)
    win.audio_channels.setEnabled(not busy)
    win.atlas_fps.setEnabled(not busy)
    win.atlas_mode.setEnabled(not busy)
    win.atlas_res.setEnabled(not busy)
    win.atlas_start.setEnabled(not busy)
    win.atlas_duration.setEnabled(not busy)
    win.btn_cancel.setEnabled(busy)


def update_action_button(win) -> None:
    if win.tabs.currentIndex() == 0:
        win.btn_action.setText(win._tr("action_convert"))
    elif win.tabs.currentIndex() == 1:
        win.btn_action.setText(win._tr("action_audio"))
    else:
        win.btn_action.setText(win._tr("action_atlas"))


def set_info_panel_visible(win, visible: bool, *, save: bool = True) -> None:
    win._info_panel_visible = visible
    win.right_panel.setVisible(visible)
    win.btn_toggle_info.blockSignals(True)
    win.btn_toggle_info.setChecked(not visible)
    win.btn_toggle_info.blockSignals(False)
    update_info_toggle_button(win)
    if visible:
        win.content_splitter.setSizes([540, 940])
    else:
        win.content_splitter.setSizes([1, 0])
    if save:
        win.save_ui_settings()


def update_info_toggle_button(win) -> None:
    if win._info_panel_visible:
        win.btn_toggle_info.setText(win._tr("hide_info_panel"))
    else:
        win.btn_toggle_info.setText(win._tr("show_info_panel"))


def update_ogv_mode_state(win) -> None:
    is_ogv = win.format.currentText().strip().lower() == "ogv"
    win.engine_profile_label.setEnabled(is_ogv)
    win.engine_profile.setEnabled(is_ogv)
    win.ogv_mode_label.setEnabled(is_ogv)
    win.ogv_mode.setEnabled(is_ogv)


def update_audio_bitrate_state(win) -> None:
    has_bitrate = win._audio_format_value() != "wav"
    win.audio_bitrate_label.setEnabled(has_bitrate)
    win.audio_bitrate.setEnabled(has_bitrate)


def reload_ogv_mode_options(win, engine_profile: str, selected: str | None = None) -> None:
    current = (selected if selected is not None else win._ogv_mode_value()).strip()
    options = list(ogv_modes_for_profile(engine_profile))
    win.ogv_mode.blockSignals(True)
    win.ogv_mode.clear()
    for option in options:
        win.ogv_mode.addItem(win._ogv_mode_label(option), option)
    idx = win.ogv_mode.findData(current)
    if idx < 0 and current:
        idx = win.ogv_mode.findText(current)
    if idx >= 0:
        win.ogv_mode.setCurrentIndex(idx)
    else:
        win.ogv_mode.setCurrentIndex(0)
    win.ogv_mode.blockSignals(False)
