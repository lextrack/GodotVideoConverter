from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable

from gvc.audio import AudioOptions, audio_extension, convert_audio
from gvc.atlas import generate_sprite_atlas
from gvc.convert import ConvertOptions, convert_video
from gvc.models import VideoInfo
from gvc.probe import probe_video


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[object], None]


@dataclass(frozen=True, slots=True)
class BatchPaths:
    ffmpeg: str
    ffprobe: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class ConvertBatchConfig:
    engine_profile: str
    fmt: str
    quality: str
    resolution: str
    fps: float
    keep_audio: bool
    ogv_mode: str


@dataclass(frozen=True, slots=True)
class AtlasBatchConfig:
    fps: int
    mode: str
    resolution: str


@dataclass(frozen=True, slots=True)
class AudioBatchConfig:
    fmt: str
    bitrate: str
    sample_rate: str
    channels: str


@dataclass(slots=True)
class ProbeCache:
    ffprobe: str
    values: dict[str, VideoInfo] = field(default_factory=dict)

    def get(self, src: str) -> VideoInfo:
        cached = self.values.get(src)
        if cached is not None:
            return cached
        info = probe_video(self.ffprobe, src)
        self.values[src] = info
        return info


def next_available_output_path(output_dir: Path, stem: str, label: str, suffix: str) -> Path:
    dst = output_dir / f"{stem}_{label}{suffix}"
    counter = 1
    while dst.exists():
        dst = output_dir / f"{stem}_{label}_{counter}{suffix}"
        counter += 1
    return dst


def convert_batch(
    inputs: list[str],
    paths: BatchPaths,
    config: ConvertBatchConfig,
    *,
    probe_cache: ProbeCache | None = None,
    cancel_event: Event | None = None,
    progress_cb: ProgressCallback | None = None,
    status_cb: StatusCallback | None = None,
) -> None:
    cache = probe_cache or ProbeCache(paths.ffprobe)
    total = len(inputs)
    ext = _extension_for_format(config.fmt)

    for idx, src in enumerate(inputs, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("conversion cancelled by user")

        source_name = Path(src).name
        _status(status_cb, "preparing_status", index=idx, total=total, name=source_name)

        info = cache.get(src)
        if is_heavy_video(info):
            _status(status_cb, "heavy_video_status", name=source_name)

        dst = next_available_output_path(paths.output_dir, Path(src).stem, "converted", ext)
        _status(status_cb, "converting_status", index=idx, total=total, name=source_name)

        convert_video(
            paths.ffmpeg,
            paths.ffprobe,
            src,
            ConvertOptions(
                output_file=str(dst),
                engine_profile=config.engine_profile,
                fmt=config.fmt,
                quality=config.quality,
                keep_audio=config.keep_audio,
                fps=config.fps,
                resolution=config.resolution,
                ogv_mode=config.ogv_mode,
            ),
            on_progress=_per_file_progress(idx, total, progress_cb),
            on_status=_convert_status_mapper(source_name, status_cb),
            cancel_event=cancel_event,
        )

    if progress_cb:
        progress_cb(100)


def generate_atlas_batch(
    inputs: list[str],
    paths: BatchPaths,
    config: AtlasBatchConfig,
    *,
    cancel_event: Event | None = None,
    progress_cb: ProgressCallback | None = None,
    status_cb: StatusCallback | None = None,
) -> None:
    total = len(inputs)

    for idx, src in enumerate(inputs, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("atlas generation cancelled by user")

        source_name = Path(src).name
        dst = next_available_output_path(paths.output_dir, Path(src).stem, "atlas", ".png")
        _status(status_cb, "atlas_status", index=idx, total=total, name=source_name)

        generate_sprite_atlas(
            paths.ffmpeg,
            paths.ffprobe,
            src,
            str(dst),
            fps=config.fps,
            mode=config.mode,
            atlas_resolution=config.resolution,
            cancel_event=cancel_event,
            on_progress=_per_file_progress(idx, total, progress_cb),
        )

    if progress_cb:
        progress_cb(100)


def convert_audio_batch(
    inputs: list[str],
    paths: BatchPaths,
    config: AudioBatchConfig,
    *,
    cancel_event: Event | None = None,
    progress_cb: ProgressCallback | None = None,
    status_cb: StatusCallback | None = None,
) -> None:
    total = len(inputs)
    ext = audio_extension(config.fmt)

    for idx, src in enumerate(inputs, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("audio conversion cancelled by user")

        source_name = Path(src).name
        dst = next_available_output_path(paths.output_dir, Path(src).stem, "audio", ext)
        _status(status_cb, "audio_status", index=idx, total=total, name=source_name)

        convert_audio(
            paths.ffmpeg,
            paths.ffprobe,
            src,
            AudioOptions(
                output_file=str(dst),
                fmt=config.fmt,
                bitrate=config.bitrate,
                sample_rate=config.sample_rate,
                channels=config.channels,
            ),
            on_progress=_per_file_progress(idx, total, progress_cb),
            on_status=_convert_status_mapper(source_name, status_cb),
            cancel_event=cancel_event,
        )

    if progress_cb:
        progress_cb(100)


def is_heavy_video(info: VideoInfo | None) -> bool:
    if not info or not getattr(info, "is_valid", False):
        return False
    return (
        info.width >= 3840
        or info.height >= 2160
        or info.frame_rate >= 50
        or (info.width >= 2560 and info.frame_rate >= 30)
    )


def _extension_for_format(fmt: str) -> str:
    return {"ogv": ".ogv", "mp4": ".mp4", "webm": ".webm", "gif": ".gif"}[fmt]


def _status(status_cb: StatusCallback | None, key: str, **kwargs) -> None:
    if status_cb:
        status_cb({"key": key, "kwargs": kwargs})


def _per_file_progress(idx: int, total: int, progress_cb: ProgressCallback | None) -> ProgressCallback:
    def _send(p: int) -> None:
        if progress_cb:
            progress_cb(int(((idx - 1) * 100 + p) / total))

    return _send


def _convert_status_mapper(source_name: str, status_cb: StatusCallback | None) -> Callable[[str], None]:
    stage_to_key = {
        "probe_input": "ffmpeg_probe_status",
        "prepare_filters": "ffmpeg_prepare_filters_status",
        "ffmpeg_launch": "ffmpeg_launch_status",
        "ffmpeg_warmup": "ffmpeg_warmup_status",
        "ffmpeg_encoding": "ffmpeg_encoding_status",
    }

    def _send(stage: str) -> None:
        key = stage_to_key.get(stage)
        if key:
            _status(status_cb, key, name=source_name)

    return _send
