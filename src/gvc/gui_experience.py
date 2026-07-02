from __future__ import annotations

import html
from pathlib import Path

from gvc.experience import ExperienceContext, guidance_html, preset_summary, summary_html


def refresh_audio_source_notice(win) -> None:
    src = win._selected_primary_path()
    if not src or not win._selected_source_is_video():
        win.audio_video_source_note.clear()
        win.audio_video_source_note.setVisible(False)
        return
    name = html.escape(Path(src).name)
    title = html.escape(win._tr("audio_video_source_title"))
    body = html.escape(win._tr("audio_video_source_body"))
    win.audio_video_source_note.setText(f"<p><b>{title}</b><br>{body}</p><p><b>{name}</b></p>")
    win.audio_video_source_note.setVisible(True)


def audio_output_preview_name(win, src: str | None) -> str:
    stem = Path(src).stem if src else "audio"
    suffix = {
        "ogg": ".ogg",
        "mp3": ".mp3",
        "aac": ".aac",
        "wav": ".wav",
    }.get(win._audio_format_value(), ".ogg")
    return f"{stem}_audio{suffix}"


def right_panel_empty_state(win) -> None:
    tab = win.tabs.currentIndex()
    body_key = {
        0: "empty_video_body",
        1: "empty_audio_body",
        2: "empty_atlas_body",
    }.get(tab, "empty_video_body")
    win.summary_text.setHtml(
        f"<h3>{html.escape(win._tr('empty_state_title'))}</h3>"
        f"<p>{html.escape(win._tr(body_key))}</p>"
    )
    win.guidance_text.setHtml(f"<p>{html.escape(win._tr('empty_state_formats'))}</p>")


def refresh_audio_right_panel(win, src: str) -> None:
    source_label = "audio_summary_video_source" if win._selected_source_is_video() else "audio_summary_audio_source"
    output = Path(win.output.text().strip() or "output") / audio_output_preview_name(win, src)
    items = [
        f"{win._tr('summary_target')}: {win._audio_format_value()}",
        f"{win._tr('audio_bitrate')}: {win._audio_bitrate_value() if win._audio_format_value() != 'wav' else win._tr('audio_bitrate_not_used')}",
        f"{win._tr('audio_sample_rate')}: {win.audio_sample_rate.currentText()}",
        f"{win._tr('audio_channels')}: {win.audio_channels.currentText()}",
        f"{win._tr('summary_output_file')}: {output}",
    ]
    win.summary_text.setHtml(
        f"<h3>{html.escape(win._tr('audio_summary_title'))}</h3>"
        f"<p><b>{html.escape(Path(src).name)}</b></p>"
        f"<p>{html.escape(win._tr(source_label))}</p>"
        f"{html_list(items)}"
    )
    win.guidance_text.clear()


def refresh_atlas_right_panel(win, src: str) -> None:
    output = Path(win.output.text().strip() or "output") / f"{Path(src).stem}_atlas.png"
    items = [
        f"{win._tr('atlas_summary_frames')}: {win.atlas_fps.value()}",
        f"{win._tr('mode')}: {win.atlas_mode.currentText()}",
        f"{win._tr('atlas_frame_size')}: {win.atlas_res.currentText()}",
        f"{win._tr('atlas_start_time')}: {win.atlas_start.value():g}s",
        f"{win._tr('atlas_duration')}: {atlas_duration_summary(win)}",
        f"{win._tr('summary_output_file')}: {output}",
    ]
    win.summary_text.setHtml(
        f"<h3>{html.escape(win._tr('atlas_summary_title'))}</h3>"
        f"<p><b>{html.escape(Path(src).name)}</b></p>"
        f"{html_list(items)}"
    )
    win.guidance_text.setHtml(f"<p>{html.escape(win._tr('atlas_summary_body'))}</p>")


def html_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def atlas_duration_summary(win) -> str:
    duration = win.atlas_duration.value()
    if duration <= 0:
        return win._tr("atlas_duration_to_end")
    return f"{duration:g}s"


def selected_video_duration(win) -> float | None:
    src = win._selected_primary_path()
    if not src or win._is_audio_only_source(src):
        return None
    try:
        info = win._cached_probe(src)
    except Exception:
        return None
    if not info.is_valid or info.duration <= 0:
        return None
    return info.duration


def sync_atlas_range_with_selected_video(win) -> None:
    src = win._selected_primary_path()
    duration = selected_video_duration(win)
    if src is None or duration is None:
        win._atlas_range_source = None
        win.atlas_start.blockSignals(True)
        win.atlas_duration.blockSignals(True)
        win.atlas_start.setMaximum(99999.0)
        win.atlas_duration.setMaximum(99999.0)
        win.atlas_start.setValue(0.0)
        win.atlas_duration.setValue(0.0)
        win.atlas_duration.blockSignals(False)
        win.atlas_start.blockSignals(False)
        return

    is_new_source = src != win._atlas_range_source
    win._atlas_range_source = src
    max_start = max(0.0, duration - 0.01)
    start = 0.0 if is_new_source else min(win.atlas_start.value(), max_start)
    remaining = max(0.01, duration - start)
    selected_duration = remaining if is_new_source else min(max(win.atlas_duration.value(), 0.01), remaining)

    win.atlas_start.blockSignals(True)
    win.atlas_duration.blockSignals(True)
    win.atlas_start.setMaximum(max_start)
    win.atlas_start.setValue(start)
    win.atlas_duration.setMaximum(remaining)
    win.atlas_duration.setValue(selected_duration)
    win.atlas_duration.blockSignals(False)
    win.atlas_start.blockSignals(False)


def on_atlas_start_changed(win) -> None:
    duration = selected_video_duration(win)
    if duration is None:
        return
    remaining = max(0.01, duration - win.atlas_start.value())
    win.atlas_duration.setMaximum(remaining)
    win.atlas_duration.setValue(remaining)


def selected_video_info(win):
    if win.tabs.currentIndex() == 1:
        return None
    src = win._selected_primary_path()
    if not src:
        return None
    try:
        return win._cached_probe(src)
    except Exception:
        return None


def experience_context(win) -> ExperienceContext:
    return ExperienceContext(
        engine_profile=win.engine_profile.currentText(),
        fmt=win.format.currentText(),
        quality=win._quality_value(),
        resolution=win.resolution.currentText().strip(),
        fps=float(win.fps.value()),
        keep_audio=win.keep_audio.isChecked(),
        ogv_mode=win._ogv_mode_value(),
        output_folder=win.output.text().strip() or "output",
        source_path=win._selected_primary_path(),
        language_code=win._lang_code(),
        keep_original_labels=frozenset(win._all_translations("keep_original")),
    )


def refresh_experience_panels(win, invalid_video_name: str | None = None) -> None:
    refresh_audio_source_notice(win)
    ctx = experience_context(win)
    title, body = preset_summary(ctx, win._tr)
    win.format_hint.clear()
    win.preset_group.setTitle(win._tr("preset_group_title"))
    win.preset_title.setText(f"<b>{html.escape(title)}</b>")
    win.preset_body.setText(f"<p>{html.escape(body)}</p>")
    src = win._selected_primary_path()
    if not src:
        right_panel_empty_state(win)
        return
    if win.tabs.currentIndex() == 1:
        refresh_audio_right_panel(win, src)
        return
    if src and win._is_audio_only_source(src):
        name = Path(src).name
        win.preset_title.setText(f"<b>{html.escape(win._tr('audio_file_selected_title'))}</b>")
        win.preset_body.setText(f"<p>{html.escape(win._tr('audio_file_selected_body'))}</p>")
        win.summary_text.setHtml(
            f"<h3>{html.escape(win._tr('audio_file_selected_title'))}</h3>"
            f"<p><b>{html.escape(name)}</b></p>"
            f"<p>{html.escape(win._tr('audio_file_selected_body'))}</p>"
        )
        win.guidance_text.clear()
        return
    if win.tabs.currentIndex() == 2:
        refresh_atlas_right_panel(win, src)
        return
    if invalid_video_name:
        win.summary_text.setHtml(summary_html(ctx, None, win._tr))
        win.guidance_text.setHtml(
            f"<p>{html.escape(win._tr('invalid_video_file', name=invalid_video_name))}</p>"
        )
        return
    info = selected_video_info(win)
    win.summary_text.setHtml(summary_html(ctx, info, win._tr))
    win.guidance_text.setHtml(guidance_html(ctx, info, win._tr))
