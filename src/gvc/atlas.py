from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass
from pathlib import Path

from gvc.probe import probe_video
from gvc.runner import run_ffmpeg


@dataclass(slots=True)
class AtlasResult:
    output_file: str
    frame_count: int
    columns: int
    rows: int
    frame_width: int
    frame_height: int


def _map_atlas_resolution(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    s = value.strip().lower()
    if s in {"low"}:
        return 64, 64
    if s in {"medium"}:
        return 128, 128
    if s in {"high"}:
        return 256, 256

    parts = s.split("x")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _fit_with_aspect(src_w: int, src_h: int, max_w: int, max_h: int) -> tuple[int, int]:
    if src_w <= 0 or src_h <= 0 or max_w <= 0 or max_h <= 0:
        return max(1, max_w), max(1, max_h)

    scale = min(max_w / src_w, max_h / src_h)
    out_w = max(1, int(src_w * scale))
    out_h = max(1, int(src_h * scale))
    return out_w, out_h


def _atlas_layout(frame_count: int, mode: str) -> tuple[int, int]:
    m = mode.strip().lower()
    if m == "horizontal":
        return max(1, frame_count), 1
    if m == "vertical":
        return 1, max(1, frame_count)
    cols = math.ceil(math.sqrt(frame_count))
    rows = math.ceil(frame_count / cols)
    return cols, rows


def _validate_output_size(cols: int, rows: int, frame_w: int, frame_h: int) -> None:
    atlas_w = cols * frame_w
    atlas_h = rows * frame_h
    if atlas_w > 16384 or atlas_h > 16384:
        raise ValueError(
            f"Atlas too large ({atlas_w}x{atlas_h}). Reduce FPS or resolution."
        )


def _generate_sprite_atlas_ffmpeg(
    ffmpeg_path: str,
    ffprobe_path: str,
    input_file: str,
    output_file: str,
    fps: int,
    mode: str,
    atlas_resolution: str | None,
    cancel_event=None,
    on_progress=None,
) -> AtlasResult:
    info = probe_video(ffprobe_path, input_file)
    if not info.is_valid:
        raise ValueError("invalid video file")

    frame_count = max(1, math.ceil(info.duration * fps))
    cols, rows = _atlas_layout(frame_count, mode)

    filters = [f"fps={fps}"]
    mapped = _map_atlas_resolution(atlas_resolution)
    frame_w = info.width
    frame_h = info.height

    if mapped:
        w, h = mapped
        frame_w, frame_h = _fit_with_aspect(info.width, info.height, w, h)
        filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")

    _validate_output_size(cols, rows, frame_w, frame_h)
    filters.append(f"tile={cols}x{rows}")

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = out.with_name(f"{out.stem}.part{out.suffix}")
    if temp_out.exists():
        temp_out.unlink()

    args = [
        "-y",
        "-i",
        input_file,
        "-frames:v",
        "1",
        "-vf",
        ",".join(filters),
        str(temp_out),
    ]
    try:
        run_ffmpeg(
            ffmpeg_path,
            args,
            total_seconds=info.duration,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )
        temp_out.replace(out)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            temp_out.unlink()
        raise

    return AtlasResult(
        output_file=str(out),
        frame_count=frame_count,
        columns=cols,
        rows=rows,
        frame_width=frame_w,
        frame_height=frame_h,
    )


def generate_sprite_atlas(
    ffmpeg_path: str,
    ffprobe_path: str,
    input_file: str,
    output_file: str,
    fps: int = 5,
    mode: str = "grid",
    atlas_resolution: str | None = "medium",
    cancel_event=None,
    on_progress=None,
) -> AtlasResult:
    src = Path(input_file)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Input file not found: {src.name}")

    if fps < 1 or fps > 30:
        raise ValueError("atlas fps must be between 1 and 30")
    return _generate_sprite_atlas_ffmpeg(
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        input_file=input_file,
        output_file=output_file,
        fps=fps,
        mode=mode,
        atlas_resolution=atlas_resolution,
        cancel_event=cancel_event,
        on_progress=on_progress,
    )
