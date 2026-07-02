from __future__ import annotations

from threading import Event
from typing import Callable

from gvc.batch import (
    AtlasBatchConfig,
    AudioBatchConfig,
    BatchPaths,
    ConvertBatchConfig,
    ProbeCache,
    convert_audio_batch,
    convert_batch,
    generate_atlas_batch,
)
from gvc.models import VideoInfo


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[object], None]
OperationJob = Callable[[Event, ProgressCallback, StatusCallback], None]


def build_convert_job(
    inputs: list[str],
    paths: BatchPaths,
    config: ConvertBatchConfig,
    cached_probe_values: dict[str, VideoInfo] | None = None,
) -> OperationJob:
    probe_cache = ProbeCache(paths.ffprobe, dict(cached_probe_values or {}))

    def _run(cancel_event: Event, progress_cb: ProgressCallback, status_cb: StatusCallback) -> None:
        convert_batch(
            inputs,
            paths,
            config,
            probe_cache=probe_cache,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
            status_cb=status_cb,
        )

    return _run


def build_audio_job(
    inputs: list[str],
    paths: BatchPaths,
    config: AudioBatchConfig,
) -> OperationJob:
    def _run(cancel_event: Event, progress_cb: ProgressCallback, status_cb: StatusCallback) -> None:
        convert_audio_batch(
            inputs,
            paths,
            config,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
            status_cb=status_cb,
        )

    return _run


def build_atlas_job(
    inputs: list[str],
    paths: BatchPaths,
    config: AtlasBatchConfig,
) -> OperationJob:
    def _run(cancel_event: Event, progress_cb: ProgressCallback, status_cb: StatusCallback) -> None:
        generate_atlas_batch(
            inputs,
            paths,
            config,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
            status_cb=status_cb,
        )

    return _run
