from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QListWidget


AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".opus",
    ".wav",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".ogv",
    ".ogg",
    ".wmv",
    ".flv",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".gif",
} | AUDIO_EXTENSIONS


@dataclass(frozen=True, slots=True)
class AddFilesResult:
    added: int = 0
    rejected: int = 0


def is_probable_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def add_files_to_list(files_widget: QListWidget, files: list[str]) -> AddFilesResult:
    existing = {files_widget.item(i).text() for i in range(files_widget.count())}
    added = 0
    rejected = 0

    for f in files:
        if not f or f in existing:
            continue
        path = Path(f)
        if not path.exists() or not path.is_file():
            continue
        if not is_probable_video_file(path):
            rejected += 1
            continue
        files_widget.addItem(f)
        existing.add(f)
        added += 1

    return AddFilesResult(added=added, rejected=rejected)


def selected_primary_path(files_widget: QListWidget) -> str | None:
    items = files_widget.selectedItems()
    if items:
        return items[0].text()
    if files_widget.count() > 0:
        return files_widget.item(0).text()
    return None


def ensure_initial_selection(files_widget: QListWidget) -> bool:
    if files_widget.count() > 0 and not files_widget.selectedItems():
        files_widget.setCurrentRow(0)
        return True
    return False


def remove_selected_files(files_widget: QListWidget, probe_cache: dict[str, object]) -> None:
    for item in files_widget.selectedItems():
        probe_cache.pop(item.text(), None)
        files_widget.takeItem(files_widget.row(item))


def clear_files(files_widget: QListWidget, probe_cache: dict[str, object]) -> None:
    files_widget.clear()
    probe_cache.clear()
