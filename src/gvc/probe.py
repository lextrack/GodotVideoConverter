from __future__ import annotations

import json
import math
import subprocess
import sys

from gvc.models import VideoInfo


def _hidden_subprocess_kwargs() -> dict[str, object]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _parse_frame_rate(raw: str) -> float:
    if not raw or "/" not in raw:
        return 0.0
    num_s, den_s = raw.split("/", 1)
    try:
        num = float(num_s)
        den = float(den_s)
        return num / den if den else 0.0
    except ValueError:
        return 0.0


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _coerce_int(value, default: int = 0) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def _coerce_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _probe_duration(fmt: dict, stream: dict) -> float:
    duration = _coerce_float(fmt.get("duration"))
    if duration > 0:
        return duration
    return _coerce_float(stream.get("duration"))


def _is_attached_picture(stream: dict) -> bool:
    disposition = stream.get("disposition") or {}
    if not isinstance(disposition, dict):
        return False
    return bool(disposition.get("attached_pic") or disposition.get("still_image"))


def probe_video(ffprobe_path: str, file_path: str) -> VideoInfo:
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_hidden_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return VideoInfo()
    if proc.returncode != 0 or not proc.stdout:
        return VideoInfo()

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return VideoInfo()
    if not isinstance(data, dict):
        return VideoInfo()

    info = VideoInfo()

    fmt = data.get("format") or {}
    if not isinstance(fmt, dict):
        fmt = {}
    info.duration = _coerce_float(fmt.get("duration"))
    info.bit_rate = _coerce_int(fmt.get("bit_rate"))

    streams = data.get("streams", [])
    if not isinstance(streams, list):
        streams = []

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type", "")
        if codec_type == "video":
            if _is_attached_picture(stream):
                continue
            info.width = _coerce_int(stream.get("width"))
            info.height = _coerce_int(stream.get("height"))
            info.video_codec = _coerce_text(stream.get("codec_name"))
            raw_frame_rate = _coerce_text(stream.get("r_frame_rate")) or _coerce_text(stream.get("avg_frame_rate"))
            info.frame_rate = _parse_frame_rate(raw_frame_rate)
            if info.duration <= 0:
                info.duration = _probe_duration(fmt, stream)
        elif codec_type == "audio":
            info.has_audio = True
            if not info.audio_codec:
                info.audio_codec = _coerce_text(stream.get("codec_name"))

    info.is_valid = (
        math.isfinite(info.duration)
        and info.duration > 0
        and info.width > 0
        and info.height > 0
    )
    return info
