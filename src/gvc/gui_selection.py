from __future__ import annotations

from pathlib import Path

from gvc.dialogs import choose_batch_scope, show_no_files
from gvc.gui_experience import sync_atlas_range_with_selected_video
from gvc.file_selection import (
    AUDIO_EXTENSIONS,
    add_files_to_list,
    clear_files,
    ensure_initial_selection,
    remove_selected_files,
    selected_primary_path,
)
from gvc.probe import probe_video


def selected_primary(win) -> str | None:
    return selected_primary_path(win.files)


def cached_probe(win, src: str):
    cached = win._probe_cache.get(src)
    if cached is not None:
        return cached
    info = probe_video(str(win.ffprobe), src)
    win._probe_cache[src] = info
    return info


def is_audio_only_source(win, src: str) -> bool:
    if Path(src).suffix.lower() in AUDIO_EXTENSIONS:
        return True
    try:
        info = cached_probe(win, src)
    except Exception:
        return False
    return bool(info.has_audio and info.width <= 0 and info.height <= 0)


def selected_source_is_video(win) -> bool:
    src = selected_primary(win)
    if not src or is_audio_only_source(win, src):
        return False
    try:
        return bool(cached_probe(win, src).is_valid)
    except Exception:
        return False


def all_file_paths(win) -> list[str]:
    return [win.files.item(i).text() for i in range(win.files.count())]


def selected_file_paths(win) -> list[str]:
    return [item.text() for item in win.files.selectedItems()]


def is_video_source(win, src: str) -> bool:
    if is_audio_only_source(win, src):
        return False
    try:
        return bool(cached_probe(win, src).is_valid)
    except Exception:
        return False


def is_audio_export_source(win, src: str) -> bool:
    if is_audio_only_source(win, src):
        return True
    try:
        info = cached_probe(win, src)
    except Exception:
        return False
    return bool(info.is_valid and info.has_audio)


def compatible_inputs_for_current_tab(win, paths: list[str]) -> list[str]:
    if win.tabs.currentIndex() == 1:
        return [src for src in paths if is_audio_export_source(win, src)]
    return [src for src in paths if is_video_source(win, src)]


def inputs_for_current_operation(win) -> list[str] | None:
    all_inputs = compatible_inputs_for_current_tab(win, all_file_paths(win))
    if not all_inputs:
        show_no_files(win, win._tr)
        return None

    selected_inputs = compatible_inputs_for_current_tab(win, selected_file_paths(win))
    if len(all_inputs) <= 1:
        return selected_inputs or all_inputs
    if selected_inputs and set(selected_inputs) == set(all_inputs):
        return all_inputs
    if not selected_inputs:
        return all_inputs

    scope = choose_batch_scope(
        win,
        win._tr,
        selected_count=len(selected_inputs),
        total_count=len(all_inputs),
    )
    if scope is None:
        return None
    return selected_inputs if scope == "selected" else all_inputs


def add_files(win, files: list[str]) -> None:
    result = add_files_to_list(win.files, files)

    if result.added == 0 and result.rejected > 0:
        win._set_status_key("no_valid_files_added")
    elif result.added > 0 and result.rejected > 0:
        win._set_status_key("added_rejected", added=result.added, rejected=result.rejected)
    elif result.added > 0:
        win._set_status_key("added_n_files", added=result.added)

    if ensure_initial_selection(win.files):
        refresh_selected_info(win)


def refresh_selected_info(win) -> None:
    src = selected_primary(win)
    sync_atlas_range_with_selected_video(win)
    if not src:
        win._refresh_experience_panels()
        return
    if win.tabs.currentIndex() == 1:
        win._refresh_experience_panels()
        return

    try:
        info = cached_probe(win, src)
        if is_audio_only_source(win, src):
            win._refresh_experience_panels()
            return
        if not info.is_valid:
            win._refresh_experience_panels(invalid_video_name=Path(src).name)
            return
        win._refresh_experience_panels()
    except Exception:
        win._refresh_experience_panels(invalid_video_name=Path(src).name)


def remove_selected(win) -> None:
    remove_selected_files(win.files, win._probe_cache)
    refresh_selected_info(win)


def clear_all(win) -> None:
    clear_files(win.files, win._probe_cache)
    refresh_selected_info(win)
    win._set_status_key("list_cleared")
