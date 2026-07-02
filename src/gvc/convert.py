from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gvc.process_utils import cleanup_temp_output, temp_output_path
from gvc.probe import probe_video
from gvc.runner import run_ffmpeg

ENGINE_PROFILE_GODOT = "Godot"
ENGINE_PROFILE_LOVE2D = "Love2D"
ENGINE_PROFILES = (ENGINE_PROFILE_GODOT, ENGINE_PROFILE_LOVE2D)

GODOT_OGV_MODES = (
    "Official Godot",
    "Seek Friendly",
    "Ideal Loop",
    "Mobile Optimized",
    "High Compression",
)

LOVE2D_OGV_MODES = (
    "Love2D Compatibility",
    "Seek Friendly",
    "Ideal Loop",
    "Lightweight",
)

OGV_QUALITY_PROFILES = {
    "ultra": ("8", "6"),
    "high": ("7", "6"),
    "balanced": ("6", "6"),
    "optimized": ("5", "5"),
    "tiny": ("4", "4"),
}


OGV_LOOP_GOP = "12"
OGV_LOOP_MIN_KEYINT = "1"
KEEP_ORIGINAL_RESOLUTION_VALUES = {
    "keep original",
    "keep_original",
    "original",
    "mantener original",
    "conserver l'original",
    "original beibehalten",
}


@dataclass(slots=True)
class ConvertOptions:
    output_file: str
    fmt: str = "ogv"
    quality: str = "optimized"
    keep_audio: bool = False
    fps: float | None = None
    resolution: str | None = None
    engine_profile: str = ENGINE_PROFILE_GODOT
    ogv_mode: str = "standard"


def _quality_key(q: str) -> str:
    return q.strip().lower()


def _gif_quality_profile(quality: str) -> tuple[int, str]:
    q = _quality_key(quality)
    profiles = {
        "ultra": (256, "sierra2_4a"),
        "high": (192, "sierra2_4a"),
        "balanced": (128, "floyd_steinberg"),
        "optimized": (96, "bayer"),
        "tiny": (64, "bayer"),
    }
    return profiles.get(q, profiles["balanced"])


def normalize_engine_profile(profile: str | None) -> str:
    p = (profile or "").strip().lower()
    if p in {"love2d", "love", "löve", "love 2d"}:
        return ENGINE_PROFILE_LOVE2D
    return ENGINE_PROFILE_GODOT


def ogv_modes_for_profile(profile: str | None) -> tuple[str, ...]:
    if normalize_engine_profile(profile) == ENGINE_PROFILE_LOVE2D:
        return LOVE2D_OGV_MODES
    return GODOT_OGV_MODES


def _ogv_quality_args(quality: str) -> tuple[list[str], list[str]]:
    q = _quality_key(quality)
    video_q, audio_q = OGV_QUALITY_PROFILES.get(q, OGV_QUALITY_PROFILES["balanced"])
    video = ["-c:v", "libtheora", "-q:v", video_q, "-threads", "0"]
    audio = ["-c:a", "libvorbis", "-q:a", audio_q, "-ar", "44100", "-ac", "2"]
    return video, audio


def _video_codec_args(fmt: str, quality: str, ogv_mode: str, engine_profile: str) -> tuple[list[str], list[str], list[str]]:
    q = _quality_key(quality)

    if fmt == "mp4":
        map_q = {
            "ultra": ["-c:v", "libx264", "-crf", "15", "-preset", "slower", "-profile:v", "high", "-level", "4.1"],
            "high": ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-level", "4.1"],
            "balanced": ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-profile:v", "main", "-level", "4.0"],
            "optimized": ["-c:v", "libx264", "-crf", "28", "-preset", "fast", "-profile:v", "main", "-level", "3.1"],
            "tiny": ["-c:v", "libx264", "-crf", "40", "-preset", "fast", "-profile:v", "baseline", "-level", "3.0"],
        }
        return map_q.get(q, map_q["balanced"]), ["-acodec", "aac", "-b:a", "128k"], ["-movflags", "+faststart"]

    if fmt == "webm":
        map_q = {
            "ultra": ["-c:v", "libvpx-vp9", "-crf", "10", "-b:v", "0", "-cpu-used", "0", "-row-mt", "1", "-tile-columns", "2"],
            "high": ["-c:v", "libvpx-vp9", "-crf", "15", "-b:v", "0", "-cpu-used", "1", "-row-mt", "1", "-tile-columns", "1"],
            "balanced": ["-c:v", "libvpx-vp9", "-crf", "25", "-b:v", "0", "-cpu-used", "2", "-row-mt", "1"],
            "optimized": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-cpu-used", "4", "-row-mt", "1"],
            "tiny": ["-c:v", "libvpx-vp9", "-crf", "48", "-b:v", "0", "-cpu-used", "5", "-deadline", "realtime"],
        }
        return map_q.get(q, map_q["balanced"]), ["-acodec", "libopus", "-b:a", "96k"], []

    if fmt == "gif":
        return [], [], ["-loop", "0"]

    godot_modes = {
        "official godot": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "48",
            "-keyint_min",
            "24",
        ],
        "seek friendly": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "24",
            "-keyint_min",
            "12",
            "-fps_mode",
            "cfr",
        ],
        "ideal loop": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            OGV_LOOP_GOP,
            "-keyint_min",
            OGV_LOOP_MIN_KEYINT,
            "-avoid_negative_ts",
            "make_zero",
            "-fflags",
            "+genpts",
        ],
        "mobile optimized": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "72",
            "-keyint_min",
            "36",
            "-fps_mode",
            "cfr",
        ],
        "high compression": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "240",
            "-keyint_min",
            "60",
        ],
        "standard": ["-pix_fmt", "yuv420p", "-g", "30", "-keyint_min", "30"],
        "constant fps (cfr)": ["-pix_fmt", "yuv420p", "-g", "15", "-keyint_min", "15", "-fps_mode", "cfr"],
        "optimized for weak hardware": ["-pix_fmt", "yuv420p", "-g", "60", "-keyint_min", "30", "-threads", "4"],
        "controlled bitrate": ["-pix_fmt", "yuv420p", "-g", "15", "-keyint_min", "5", "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "2000k"],
    }
    love2d_modes = {
        "love2d compatibility": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "24",
            "-keyint_min",
            "12",
            "-fps_mode",
            "cfr",
        ],
        "seek friendly": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "12",
            "-keyint_min",
            "6",
            "-fps_mode",
            "cfr",
        ],
        "ideal loop": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            OGV_LOOP_GOP,
            "-keyint_min",
            OGV_LOOP_MIN_KEYINT,
            "-avoid_negative_ts",
            "make_zero",
            "-fflags",
            "+genpts",
        ],
        "lightweight": [
            "-pix_fmt",
            "yuv420p",
            "-g",
            "72",
            "-keyint_min",
            "36",
        ],
        # Backward compatibility if an older config is reused under Love2D only.
        "standard": ["-pix_fmt", "yuv420p", "-g", "24", "-keyint_min", "12"],
    }

    profile = normalize_engine_profile(engine_profile)
    mode_key = ogv_mode.strip().lower()
    video, audio = _ogv_quality_args(quality)
    if profile == ENGINE_PROFILE_LOVE2D:
        extra = list(love2d_modes.get(mode_key, love2d_modes["love2d compatibility"]))
    else:
        extra = list(godot_modes.get(mode_key, godot_modes["official godot"]))

    if "-fps_mode" not in extra:
        extra.extend(["-fps_mode", "cfr"])
    return video, audio, extra


def _parse_resolution(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    s = value.strip().lower()
    if s in KEEP_ORIGINAL_RESOLUTION_VALUES:
        return None
    parts = s.split("x")
    if len(parts) != 2:
        return None
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def validate_resolution(value: str | None) -> None:
    if not value:
        return
    s = value.strip().lower()
    if not s or s in KEEP_ORIGINAL_RESOLUTION_VALUES:
        return
    if _parse_resolution(value) is None:
        raise ValueError("output resolution must use WIDTHxHEIGHT, for example 1280x720")


def _build_filter_chain(fmt: str, fps: float | None, resolution: str | None, quality: str) -> str | None:
    filters: list[str] = []

    parsed = _parse_resolution(resolution)
    if parsed:
        w, h = parsed
        if fmt == "mp4":
            filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
            filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        else:
            filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")

    if fmt == "ogv":
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

    if fps and fps > 0:
        filters.append(f"fps={fps}")

    if fmt == "gif":
        if not fps:
            fps = 20
        max_colors, dither = _gif_quality_profile(quality)
        gif_chain = [f"fps={fps}"]
        if parsed:
            w, h = parsed
            gif_chain.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        gif_chain.append("scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos")
        gif_chain.append("split[s0][s1]")
        gif_chain.append(f"[s0]palettegen=max_colors={max_colors}:stats_mode=diff[p]")
        if dither == "bayer":
            gif_chain.append("[s1][p]paletteuse=dither=bayer:bayer_scale=5")
        else:
            gif_chain.append(f"[s1][p]paletteuse=dither={dither}")
        return ",".join(gif_chain)

    return ",".join(filters) if filters else None


def _validate_video_fps(fps: float | None) -> None:
    if fps is None:
        return
    if fps < 1 or fps > 60:
        raise ValueError("video fps must be between 1 and 60")


def convert_video(
    ffmpeg_path: str,
    ffprobe_path: str,
    input_file: str,
    options: ConvertOptions,
    on_progress=None,
    on_status=None,
    cancel_event=None,
) -> str:
    src = Path(input_file)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Input file not found: {src.name}")
    _validate_video_fps(options.fps)
    validate_resolution(options.resolution)

    final_out = Path(options.output_file)
    final_out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = temp_output_path(final_out)
    cleanup_temp_output(temp_out)

    if on_status:
        on_status("probe_input")
    info = probe_video(ffprobe_path, input_file)
    total_seconds = info.duration if info.duration > 0 else None

    codec_video, codec_audio, extra = _video_codec_args(options.fmt, options.quality, options.ogv_mode, options.engine_profile)
    if not options.keep_audio or options.fmt == "gif":
        codec_audio = ["-an"]

    if on_status:
        on_status("prepare_filters")
    filter_chain = _build_filter_chain(options.fmt, options.fps, options.resolution, options.quality)

    args = ["-y", "-i", input_file]
    if filter_chain:
        args.extend(["-vf", filter_chain])

    args.extend(codec_video)
    args.extend(codec_audio)
    args.extend(extra)
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
        cleanup_temp_output(temp_out)
        raise
