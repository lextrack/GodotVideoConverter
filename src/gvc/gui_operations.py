from __future__ import annotations

from gvc.batch import AtlasBatchConfig, AudioBatchConfig, BatchPaths, ConvertBatchConfig
from gvc.batch_jobs import build_atlas_job, build_audio_job, build_convert_job
from gvc.dialogs import show_invalid_fps


def start_convert(win) -> None:
    inputs = win._inputs_for_current_operation()
    if inputs is None:
        return

    try:
        fps_val = float(win.fps.value())
    except ValueError as exc:
        show_invalid_fps(win, win._tr, str(exc))
        return

    output = win._ensure_output_directory(notify=True)
    if output is None:
        return
    resolution = win._validate_resolution_from_ui()
    if resolution is None:
        return

    paths = BatchPaths(ffmpeg=str(win.ffmpeg), ffprobe=str(win.ffprobe), output_dir=output)
    config = ConvertBatchConfig(
        engine_profile=win.engine_profile.currentText(),
        fmt=win.format.currentText(),
        quality=win._quality_value(),
        resolution=resolution,
        fps=fps_val,
        keep_audio=win.keep_audio.isChecked(),
        ogv_mode=win._ogv_mode_value(),
    )
    win._start_worker(
        build_convert_job(
            inputs,
            paths,
            config,
            {src: win._probe_cache[src] for src in inputs if src in win._probe_cache},
        )
    )


def start_audio(win) -> None:
    inputs = win._inputs_for_current_operation()
    if inputs is None:
        return

    output = win._ensure_output_directory(notify=True)
    if output is None:
        return

    paths = BatchPaths(ffmpeg=str(win.ffmpeg), ffprobe=str(win.ffprobe), output_dir=output)
    config = AudioBatchConfig(
        fmt=win._audio_format_value(),
        bitrate=win._audio_bitrate_value(),
        sample_rate=win._audio_sample_rate_value(),
        channels=win._audio_channels_value(),
    )
    win._start_worker(build_audio_job(inputs, paths, config))


def start_atlas(win) -> None:
    inputs = win._inputs_for_current_operation()
    if inputs is None:
        return

    output = win._ensure_output_directory(notify=True)
    if output is None:
        return

    paths = BatchPaths(ffmpeg=str(win.ffmpeg), ffprobe=str(win.ffprobe), output_dir=output)
    config = AtlasBatchConfig(
        fps=win.atlas_fps.value(),
        mode=win._atlas_mode_value(),
        resolution=win._atlas_resolution_value(),
        start_time=win.atlas_start.value(),
        duration=win.atlas_duration.value(),
    )
    win._start_worker(build_atlas_job(inputs, paths, config))
