from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


class FFmpegNotFoundError(FileNotFoundError):
    pass


def _is_windows() -> bool:
    return os.name == "nt"


def _binary_name(base: str) -> str:
    return f"{base}.exe" if _is_windows() else base


def _candidate_dirs() -> list[Path]:
    candidates: list[Path] = []

    env_dir = os.getenv("GVC_FFMPEG_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    exe_dir = Path(sys.executable).resolve().parent
    candidates.extend([exe_dir / "bin", exe_dir])

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        m = Path(meipass)
        candidates.extend([m / "bin", m])

    here = Path(__file__).resolve()
    project_root = here.parents[2]
    candidates.extend(
        [
            project_root / "bin",
            project_root,
            project_root.parent / "bin",
        ]
    )

    seen: set[str] = set()
    unique: list[Path] = []
    for c in candidates:
        key = str(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def resolve_binary(name: str) -> Path:
    binary = _binary_name(name)

    for directory in _candidate_dirs():
        candidate = directory / binary
        if candidate.exists() and candidate.is_file():
            return candidate

    path_result = shutil.which(binary)
    if path_result:
        return Path(path_result)

    searched = "\n".join(str(p) for p in _candidate_dirs())
    raise FFmpegNotFoundError(
        f"Could not find {binary}. Searched in:\n{searched}\nAlso checked PATH."
    )


def resolve_ffmpeg_and_ffprobe() -> tuple[Path, Path]:
    return resolve_binary("ffmpeg"), resolve_binary("ffprobe")
