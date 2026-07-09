from __future__ import annotations

from pathlib import Path

from gvc.dialogs import choose_batch_scope, show_no_files
from gvc.gui_experience import sync_atlas_range_with_selected_video
from gvc.file_selection import (
    add_files_to_list,
    clear_files,
    ensure_initial_selection,
    remove_selected_files,
    selected_primary_path,
)
from gvc.operation_selection import (
    MediaKind,
    OperationKind,
    detect_media_kind,
    evaluate_sources_for_operation,
    evaluate_source_for_operation,
    operation_for_tab_index,
    resolve_operation_inputs,
    summarize_ineligible_results,
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
    return detect_media_kind(src, probe=lambda path: cached_probe(win, path)) == MediaKind.AUDIO_ONLY


def selected_source_is_video(win) -> bool:
    src = selected_primary(win)
    if not src:
        return False
    return detect_media_kind(src, probe=lambda path: cached_probe(win, path)) == MediaKind.VIDEO


def all_file_paths(win) -> list[str]:
    return [win.files.item(i).text() for i in range(win.files.count())]


def selected_file_paths(win) -> list[str]:
    return [item.text() for item in win.files.selectedItems()]


def is_video_source(win, src: str) -> bool:
    result = evaluate_source_for_operation(
        src,
        OperationKind.CONVERT_VIDEO,
        probe=lambda path: cached_probe(win, path),
    )
    return result.allowed


def is_audio_export_source(win, src: str) -> bool:
    result = evaluate_source_for_operation(
        src,
        OperationKind.CONVERT_AUDIO,
        probe=lambda path: cached_probe(win, path),
    )
    return result.allowed


def compatible_inputs_for_operation(win, paths: list[str], operation: OperationKind) -> list[str]:
    return [
        src
        for src in paths
        if evaluate_source_for_operation(
            src,
            operation,
            probe=lambda path: cached_probe(win, path),
        ).allowed
    ]


def compatible_inputs_for_current_tab(win, paths: list[str]) -> list[str]:
    return compatible_inputs_for_operation(win, paths, operation_for_tab_index(win.tabs.currentIndex()))


def inputs_for_operation(win, operation: OperationKind) -> list[str] | None:
    all_paths = all_file_paths(win)
    inputs = resolve_operation_inputs(
        all_paths,
        selected_file_paths(win),
        operation,
        probe=lambda path: cached_probe(win, path),
        choose_scope=lambda selected_count, total_count: choose_batch_scope(
            win,
            win._tr,
            selected_count=selected_count,
            total_count=total_count,
        ),
    )
    if inputs == []:
        results = evaluate_sources_for_operation(
            all_paths,
            operation,
            probe=lambda path: cached_probe(win, path),
        )
        details = [
            win._tr("no_files_reason_line", count=count, reason=win._tr(f"eligibility_reason_{reason}"))
            for reason, count in summarize_ineligible_results(results)
        ]
        show_no_files(win, win._tr, details=details)
        return None
    return inputs


def inputs_for_current_operation(win) -> list[str] | None:
    return inputs_for_operation(win, operation_for_tab_index(win.tabs.currentIndex()))


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
