from __future__ import annotations

import contextlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from gvc.runner import run_ffmpeg


AUDIO_FORMATS = ("ogg", "mp3", "aac", "wav")
AUDIO_BITRATES = ("96k", "128k", "160k", "192k", "256k", "320k")
AUDIO_SAMPLE_RATES = ("keep", "44100", "48000")
AUDIO_CHANNELS = ("keep", "mono", "stereo")


@dataclass(slots=True)
class AudioOptions:
    output_file: str
    fmt: str = "ogg"
    bitrate: str = "160k"
    sample_rate: str = "44100"
    channels: str = "stereo"


def _hidden_subprocess_kwargs() -> dict[str, object]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def probe_audio_duration(ffprobe_path: str, file_path: str) -> float:
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
        return 0.0
    if proc.returncode != 0 or not proc.stdout:
        return 0.0

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(data, dict):
        return 0.0

    fmt = data.get("format") or {}
    duration = _coerce_duration(fmt.get("duration") if isinstance(fmt, dict) else None)
    if duration > 0:
        return duration

    streams = data.get("streams", [])
    if not isinstance(streams, list):
        return 0.0
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "audio":
            continue
        duration = _coerce_duration(stream.get("duration"))
        if duration > 0:
            return duration
    return 0.0


def convert_audio(
    ffmpeg_path: str,
    ffprobe_path: str,
    input_file: str,
    options: AudioOptions,
    on_progress=None,
    on_status=None,
    cancel_event=None,
) -> str:
    src = Path(input_file)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Input file not found: {src.name}")

    fmt = normalize_audio_format(options.fmt)
    bitrate = normalize_audio_bitrate(options.bitrate)
    sample_rate = normalize_sample_rate(options.sample_rate)
    channels = normalize_channels(options.channels)

    final_out = Path(options.output_file)
    final_out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = final_out.with_name(f"{final_out.stem}.part{final_out.suffix}")
    if temp_out.exists():
        temp_out.unlink()

    if on_status:
        on_status("probe_input")
    total_seconds = probe_audio_duration(ffprobe_path, input_file) or None

    if on_status:
        on_status("prepare_filters")
    args = ["-y", "-i", input_file, "-vn"]
    args.extend(_audio_codec_args(fmt, bitrate))
    if sample_rate:
        args.extend(["-ar", sample_rate])
    if channels:
        args.extend(["-ac", channels])
    args.append(str(temp_out))

    try:
        run_ffmpeg(
            ffmpeg_path,
            args,
            total_seconds=total_seconds,
            on_progress=on_progress,
            on_status=on_status,
            cancel_event=cancel_event,
        )
        temp_out.replace(final_out)
        return str(final_out)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            temp_out.unlink()
        raise


def audio_extension(fmt: str) -> str:
    return {
        "ogg": ".ogg",
        "mp3": ".mp3",
        "aac": ".aac",
        "wav": ".wav",
    }[normalize_audio_format(fmt)]


def normalize_audio_format(value: str | None) -> str:
    fmt = (value or "").strip().lower()
    return fmt if fmt in AUDIO_FORMATS else "ogg"


def normalize_audio_bitrate(value: str | None) -> str:
    bitrate = (value or "").strip().lower()
    return bitrate if bitrate in AUDIO_BITRATES else "160k"


def normalize_sample_rate(value: str | None) -> str | None:
    sample_rate = (value or "").strip().lower()
    if sample_rate in {"", "keep", "original"}:
        return None
    return sample_rate if sample_rate in {"44100", "48000"} else "44100"


def normalize_channels(value: str | None) -> str | None:
    channels = (value or "").strip().lower()
    if channels in {"", "keep", "original"}:
        return None
    return {"mono": "1", "stereo": "2"}.get(channels, "2")


def _audio_codec_args(fmt: str, bitrate: str) -> list[str]:
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", bitrate]
    if fmt == "aac":
        return ["-c:a", "aac", "-b:a", bitrate]
    if fmt == "wav":
        return ["-c:a", "pcm_s16le"]
    return ["-c:a", "libvorbis", "-b:a", bitrate]


def _coerce_duration(value) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(duration):
        return 0.0
    return max(duration, 0.0)
