from __future__ import annotations

from dataclasses import dataclass, field

from gvc.i18n import translate_recommendations
from gvc.models import VideoInfo
from gvc.convert import ENGINE_PROFILE_LOVE2D, normalize_engine_profile


@dataclass
class _State:
    what_has: list[str] = field(default_factory=list)
    next_step: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecommendationSections:
    what_has: tuple[str, ...] = ()
    next_step: tuple[str, ...] = ()


def _gcd(a: int, b: int) -> int:
    while b != 0:
        a, b = b, a % b
    return a


def _aspect_ratio(video: VideoInfo) -> str:
    if video.width <= 0 or video.height <= 0:
        return "Unknown"
    gcd = _gcd(video.width, video.height)
    w = video.width // gcd
    h = video.height // gcd
    key = f"{w}:{h}"
    if key in {"16:9", "4:3", "1:1", "21:9", "3:2"}:
        return key
    return key


def _codec_family(codec: str) -> str:
    c = (codec or "").strip().lower()
    if not c:
        return "unknown"
    if c in {"theora"} or "theora" in c:
        return "ogv"
    if c in {"h264", "avc1", "avc"} or "h264" in c:
        return "mp4"
    if c in {"vp9", "vp8"} or "vp9" in c or "vp8" in c:
        return "webm"
    if c in {"gif"} or "gif" in c:
        return "gif"
    return "other"


def _audio_family(codec: str) -> str:
    c = (codec or "").strip().lower()
    if not c:
        return "unknown"
    if c in {"aac"} or "aac" in c:
        return "aac"
    if c in {"vorbis"} or "vorbis" in c:
        return "vorbis"
    if c in {"opus"} or "opus" in c:
        return "opus"
    if c in {"mp3"} or "mp3" in c:
        return "mp3"
    if c in {"pcm", "wav"} or "pcm" in c:
        return "pcm"
    return "other"


def _append_common_video_findings(s: _State, video: VideoInfo) -> None:
    source_name = video.video_codec or "unknown"
    family = _codec_family(video.video_codec)
    if family == "ogv":
        s.what_has.append(f"Source video codec: {source_name} - already in the OGV/Theora family")
    elif family == "mp4":
        s.what_has.append(f"Source video codec: {source_name} - common source format for exported videos")
    elif family == "webm":
        s.what_has.append(f"Source video codec: {source_name} - web-oriented source video format")
    elif family == "gif":
        s.what_has.append(f"Source video codec: {source_name} - animated image style source")
    else:
        s.what_has.append(f"Source video codec: {source_name}")


def _append_common_audio_findings(s: _State, video: VideoInfo) -> None:
    if not video.has_audio:
        return
    source_name = video.audio_codec or "unknown"
    family = _audio_family(video.audio_codec)
    if family == "aac":
        s.what_has.append(f"Source audio codec: {source_name} - common in MP4 exports")
    elif family == "vorbis":
        s.what_has.append(f"Source audio codec: {source_name} - already close to OGV workflows")
    elif family == "opus":
        s.what_has.append(f"Source audio codec: {source_name} - efficient web-oriented audio")
    elif family == "mp3":
        s.what_has.append(f"Source audio codec: {source_name} - common compressed audio")
    elif family == "pcm":
        s.what_has.append(f"Source audio codec: {source_name} - uncompressed or near-uncompressed audio")
    else:
        s.what_has.append(f"Source audio codec: {source_name}")


def _append_common_aspect_guidance(s: _State, ar: str) -> None:
    if ar == "16:9":
        s.what_has.append("Widescreen (16:9) - Easy fit for fullscreen scenes and cutscenes")
    elif ar == "4:3":
        s.what_has.append("Classic 4:3 - Useful for retro presentation or stylized UI")
    elif ar == "1:1":
        s.what_has.append("Square (1:1) - Useful for UI, icons, or centered loops")
    elif ar == "21:9":
        s.what_has.append("Ultra-wide (21:9) - May need letterboxing or careful layout")
    else:
        s.what_has.append("Non-standard aspect ratio - May need cropping, padding, or a custom layout")


def _translate_sections(s: _State, language: str) -> RecommendationSections:
    return RecommendationSections(
        what_has=tuple(translate_recommendations(item, language) for item in s.what_has),
        next_step=tuple(translate_recommendations(item, language) for item in s.next_step),
    )


def _format_recommendation_sections(sections: RecommendationSections, language: str, fallback: str) -> str:
    blocks: list[str] = []
    if sections.what_has:
        title = translate_recommendations("WHAT THIS VIDEO HAS", language)
        blocks.append(title + "\n" + "\n".join(f"- {x}" for x in sections.what_has))
    if sections.next_step:
        title = translate_recommendations("RECOMMENDED NEXT STEP", language)
        blocks.append(title + "\n" + "\n".join(f"- {x}" for x in sections.next_step))

    if not blocks:
        return translate_recommendations(fallback, language)
    return "\n\n".join(blocks)


def _build_godot_recommendation_state(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
) -> _State:
    if not video.is_valid:
        return _State(next_step=["Invalid video file"])

    s = _State()

    if video.duration <= 10:
        s.what_has.append("Short video (0-10s) - Perfect for UI animations or button effects")
        s.next_step.append("Use 'Ideal Loop' only when seamless repetition matters more than file size")
        if video.frame_rate < 30:
            s.next_step.append("Increase to 30 FPS for smoother UI animations")
    elif video.duration <= 30:
        s.what_has.append("Medium video (10-30s) - Ideal for character animations or environmental loops")
        s.next_step.append("Try 'Official Godot' as the recommended starting point")
    elif video.duration <= 60:
        s.what_has.append("Long video (30-60s) - Great for cutscenes or character intros")
        s.next_step.append("Start with 'Official Godot'; use 'High Compression' only if file size matters more than quick seeking")
    elif video.duration <= 180:
        s.what_has.append("Extended video (60-180s) - Suitable for intro cinematics or tutorials")
        s.next_step.append("Split into shorter clips for faster loading in Godot")
        s.next_step.append("Use 'Mobile Optimized' for steadier playback, or 'High Compression' if size is the main concern")
    else:
        s.what_has.append("Very long video (180s+) - May impact loading times")
        s.next_step.append("Large files possible with OGV; reduce resolution or FPS")
        s.next_step.append("Split into smaller clips or stream externally")
        s.next_step.append("Avoid 'Ideal Loop' on long videos unless the clip is very short and truly loop-focused")

    if video.width > 1920 or video.height > 1080:
        s.what_has.append("High resolution detected")
        s.next_step.append("Large files possible with OGV; try 1080p or 720p to save space")
        if video.duration <= 30:
            s.what_has.append("High-res is fine for short splash screens or cutscenes")
        else:
            s.next_step.append("Use 1080p for most Godot projects, or 720p for mobiles")
    elif video.width <= 854 and video.height <= 480:
        s.what_has.append("Low resolution - Great for mobile or retro-style games")
        s.next_step.append("Use 'Mobile Optimized' for more predictable playback")
    else:
        s.what_has.append("Standard resolution - Suitable for most Godot projects")
        s.next_step.append("Try 720p for mobiles or 1080p for desktop")

    if video.frame_rate > 60:
        if video.duration <= 5:
            s.what_has.append("High FPS short clip - Great for smooth UI effects")
        else:
            s.what_has.append("High FPS detected")
            s.next_step.append("Reduce to 30 FPS to save space with OGV")
    elif video.frame_rate < 24:
        s.what_has.append("Low FPS detected")
        s.next_step.append("Use 24-30 FPS for smooth cinematics or gameplay")
    else:
        s.what_has.append("24-30 FPS is ideal for OGV in Godot - balances smoothness and size")

    if video.has_audio:
        if video.duration <= 5:
            s.what_has.append("Short video with audio (0-5s) - Perfect for UI sounds or effects")
        elif video.duration > 60:
            s.what_has.append("Long video with audio - Great for cutscenes")
            s.next_step.append("Extract audio as OGG for better control in Godot")
        else:
            s.what_has.append("Audio included - Good for character dialogues or ambient scenes")
            s.next_step.append("Consider extracting audio as OGG for flexible control in Godot")

        if not keep_audio:
            s.next_step.append("Audio will be removed because keep_audio is disabled")
    else:
        s.what_has.append("No audio - Ideal for background loops or visual effects")
        s.next_step.append("Use OGV for best compatibility in Godot")

    _append_common_video_findings(s, video)
    _append_common_audio_findings(s, video)

    ar = _aspect_ratio(video)
    _append_common_aspect_guidance(s, ar)

    source_family = _codec_family(video.video_codec)
    target = (target_format or "ogv").strip().lower()
    source_name = video.video_codec or "unknown"

    if target == "ogv":
        if source_family == "ogv":
            s.what_has.append(f"Source codec ({source_name}) is already OGV-compatible for Godot")
            s.next_step.append("You may not need to reconvert unless you want a different size or preset")
        else:
            s.next_step.append(
                f"Converting from {source_name} to OGV is recommended for Godot compatibility"
            )
            if source_family == "mp4":
                s.next_step.append("H.264/AVC sources usually convert cleanly to Godot-oriented OGV")
            elif source_family == "webm":
                s.next_step.append("WebM sources can work as inputs, but OGV is the safer final target for Godot")
            elif source_family == "gif":
                s.next_step.append("Animated GIF sources usually benefit from lower resolution or lower FPS before export")
        s.next_step.append("Use 'Seek Friendly' if the video needs to start from different points")
        if video.duration > 60:
            s.next_step.append("For longer clips, prefer 'Official Godot', 'Mobile Optimized', or 'High Compression' before trying 'Ideal Loop'")
    elif target == "mp4":
        s.next_step.append(
            "MP4 output selected. This is fine for general use, but OGV is recommended for Godot runtime compatibility"
        )
    elif target == "webm":
        s.next_step.append(
            "WebM output selected. This is fine for general use, but OGV is recommended for Godot runtime compatibility"
        )
    elif target == "gif":
        s.next_step.append(
            "GIF output selected. Useful for previews/UI loops, but OGV is recommended for in-game video playback in Godot"
        )
    else:
        s.next_step.append("OGV is the format natively supported by Godot")

    return s


def get_godot_recommendation_sections(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> RecommendationSections:
    return _translate_sections(
        _build_godot_recommendation_state(
            video,
            keep_audio=keep_audio,
            target_format=target_format,
        ),
        language,
    )


def get_godot_recommendations(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> str:
    sections = get_godot_recommendation_sections(
        video,
        keep_audio=keep_audio,
        target_format=target_format,
        language=language,
    )
    return _format_recommendation_sections(
        sections,
        language,
        "Video looks good for Godot. Use OGV for best compatibility.",
    )


def _build_love2d_recommendation_state(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
) -> _State:
    if not video.is_valid:
        return _State(next_step=["Invalid video file"])

    s = _State()

    if video.duration <= 10:
        s.what_has.append("Short video (0-10s) - Good for loops, UI effects, or stylized inserts")
        s.next_step.append("Use 'Ideal Loop' only when the clip is short and the repeat must feel seamless")
    elif video.duration <= 60:
        s.what_has.append("Medium video (10-60s) - Suitable for in-game scenes or animated screens")
    else:
        s.what_has.append("Long video (60s+) - Test playback early on target hardware")
        s.next_step.append("Long videos are easier to manage when split into shorter scenes")
        s.next_step.append("Start with 'Love2D Compatibility' or 'Lightweight' before trying more aggressive loop settings")

    if video.width > 1920 or video.height > 1080:
        s.what_has.append("High resolution detected")
        s.next_step.append("Prefer 1080p or 720p unless the game really needs a larger source")
    elif video.width <= 854 and video.height <= 480:
        s.what_has.append("Low resolution - Good fit for lightweight 2D projects")
    else:
        s.what_has.append("Standard resolution - Good baseline for Love2D playback")

    if video.frame_rate > 30:
        s.next_step.append("Reduce to 24-30 FPS if you want a lighter OGV for Love2D")
    elif video.frame_rate < 20:
        s.what_has.append("Very low FPS may look choppy; 24-30 FPS is a safer default")
    else:
        s.what_has.append("24-30 FPS is a practical target for Love2D video playback")

    if video.has_audio:
        if not keep_audio:
            s.next_step.append("Audio will be removed because keep_audio is disabled")
        else:
            s.what_has.append("Embedded audio is supported, but test sync and volume on target platforms")
    else:
        s.what_has.append("No audio - Good for decorative loops or background motion")

    _append_common_video_findings(s, video)
    _append_common_audio_findings(s, video)

    source_family = _codec_family(video.video_codec)
    source_name = video.video_codec or "unknown"
    ar = _aspect_ratio(video)
    _append_common_aspect_guidance(s, ar)
    target = (target_format or "ogv").strip().lower()
    if target == "ogv":
        if source_family == "ogv":
            s.what_has.append(f"Source codec ({source_name}) is already OGV-compatible for Love2D")
            s.next_step.append("You may not need to reconvert unless you want a smaller file or a different preset")
        else:
            s.next_step.append(
                f"Converting from {source_name} to OGV is recommended for Love2D compatibility"
            )
            if source_family == "mp4":
                s.next_step.append("H.264/AVC sources are a practical starting point before converting to OGV")
            elif source_family == "webm":
                s.next_step.append("WebM sources are fine as inputs, but OGV is the safer final target for Love2D")
            elif source_family == "gif":
                s.next_step.append("Animated GIF sources usually benefit from lower resolution or lower FPS before export")
        s.next_step.append("If a file fails in Love2D, try 'Love2D Compatibility' first")
        s.next_step.append("Use 'Seek Friendly' if the video needs to start from different points")
        s.next_step.append("Use 'Lightweight' if you want a smaller file")
        if video.duration > 60:
            s.next_step.append("Avoid 'Ideal Loop' on longer Love2D clips unless the video is a short decorative loop")
    elif target == "mp4":
        s.next_step.append("MP4 output selected. Keep OGV for the final Love2D playback path")
    elif target == "webm":
        s.next_step.append("WebM output selected. Keep OGV for the final Love2D playback path")
    elif target == "gif":
        s.next_step.append("GIF output selected. Fine for previews, but not as a Love2D video replacement")
    else:
        s.next_step.append("OGV is the main engine-oriented target for Love2D video playback")

    return s


def get_love2d_recommendation_sections(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> RecommendationSections:
    return _translate_sections(
        _build_love2d_recommendation_state(
            video,
            keep_audio=keep_audio,
            target_format=target_format,
        ),
        language,
    )


def get_love2d_recommendations(
    video: VideoInfo,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> str:
    sections = get_love2d_recommendation_sections(
        video,
        keep_audio=keep_audio,
        target_format=target_format,
        language=language,
    )
    return _format_recommendation_sections(
        sections,
        language,
        "Video looks good for Love2D. Use OGV for best compatibility.",
    )


def get_engine_recommendations(
    video: VideoInfo,
    engine_profile: str,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> str:
    if normalize_engine_profile(engine_profile) == ENGINE_PROFILE_LOVE2D:
        return get_love2d_recommendations(
            video,
            keep_audio=keep_audio,
            target_format=target_format,
            language=language,
        )
    return get_godot_recommendations(
        video,
        keep_audio=keep_audio,
        target_format=target_format,
        language=language,
    )


def get_engine_recommendation_sections(
    video: VideoInfo,
    engine_profile: str,
    keep_audio: bool = True,
    target_format: str = "ogv",
    language: str = "en",
) -> RecommendationSections:
    if normalize_engine_profile(engine_profile) == ENGINE_PROFILE_LOVE2D:
        return get_love2d_recommendation_sections(
            video,
            keep_audio=keep_audio,
            target_format=target_format,
            language=language,
        )
    return get_godot_recommendation_sections(
        video,
        keep_audio=keep_audio,
        target_format=target_format,
        language=language,
    )
