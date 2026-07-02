from __future__ import annotations

from gvc.gui_experience import refresh_audio_source_notice
from gvc.ui_panels import AUDIO_CHANNEL_OPTIONS, AUDIO_FORMAT_OPTIONS, AUDIO_SAMPLE_RATE_OPTIONS, QUALITY_OPTIONS


def apply_language(win) -> None:
    win.setWindowTitle(win._tr("window_title"))
    win.btn_add.setText(win._tr("add_files"))
    win.btn_remove.setText(win._tr("remove_selected"))
    win.btn_clear.setText(win._tr("clear"))
    win.files_group.setTitle(win._tr("files_group_title"))
    win.files_hint.setText(win._tr("files_drop_hint"))
    win._update_info_toggle_button()
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
    win.audio_format_label.setText(win._tr("format"))
    win.audio_bitrate_label.setText(win._tr("audio_bitrate"))
    win.audio_sample_rate_label.setText(win._tr("audio_sample_rate"))
    win.audio_channels_label.setText(win._tr("audio_channels"))
    win.audio_guidance_group.setTitle(win._tr("audio_guidance_group"))
    win.audio_guidance_title.setText(f"<b>{win._tr('audio_guidance_title')}</b>")
    win.audio_guidance_body.setText(win._tr("audio_guidance_body"))
    refresh_audio_source_notice(win)
    reload_audio_format_options(win)
    reload_audio_sample_rate_options(win)
    reload_audio_channel_options(win)
    win.frames_label.setText(win._tr("frames"))
    win.mode_label.setText(win._tr("mode"))
    win.atlas_resolution_label.setText(win._tr("atlas_frame_size"))
    win.atlas_range_label.setText(win._tr("atlas_range"))
    win.atlas_start_label.setText(win._tr("atlas_start_time"))
    win.atlas_duration_label.setText(win._tr("atlas_duration"))
    win.atlas_duration_hint.setText(win._tr("atlas_duration_hint"))
    win.rec_group.setTitle(win._tr("rec_title"))
    win.btn_cancel.setText(win._tr("cancel"))
    win.tabs.setTabText(0, win._tr("tab_convert"))
    win.tabs.setTabText(1, win._tr("tab_audio"))
    win.tabs.setTabText(2, win._tr("tab_atlas"))
    win._reload_ogv_mode_options(win.engine_profile.currentText(), win._ogv_mode_value())
    win._reload_atlas_mode_options(win._atlas_mode_value())
    win._reload_atlas_resolution_options(win._atlas_resolution_value())
    win._update_audio_bitrate_state()
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


def reload_audio_format_options(win) -> None:
    current = win._audio_format_value()
    win.audio_format.blockSignals(True)
    win.audio_format.clear()
    for fmt in AUDIO_FORMAT_OPTIONS:
        win.audio_format.addItem(win._tr(f"audio_format_{fmt}"), fmt)
    idx = win.audio_format.findData(current)
    win.audio_format.setCurrentIndex(idx if idx >= 0 else 0)
    win.audio_format.blockSignals(False)


def reload_audio_sample_rate_options(win) -> None:
    current = win._audio_sample_rate_value()
    win.audio_sample_rate.blockSignals(True)
    win.audio_sample_rate.clear()
    for sample_rate in AUDIO_SAMPLE_RATE_OPTIONS:
        key = "audio_sample_keep" if sample_rate == "keep" else f"audio_sample_{sample_rate}"
        win.audio_sample_rate.addItem(win._tr(key), sample_rate)
    idx = win.audio_sample_rate.findData(current)
    win.audio_sample_rate.setCurrentIndex(idx if idx >= 0 else 1)
    win.audio_sample_rate.blockSignals(False)


def reload_audio_channel_options(win) -> None:
    current = win._audio_channels_value()
    win.audio_channels.blockSignals(True)
    win.audio_channels.clear()
    for channels in AUDIO_CHANNEL_OPTIONS:
        win.audio_channels.addItem(win._tr(f"audio_channels_{channels}"), channels)
    idx = win.audio_channels.findData(current)
    win.audio_channels.setCurrentIndex(idx if idx >= 0 else 2)
    win.audio_channels.blockSignals(False)
