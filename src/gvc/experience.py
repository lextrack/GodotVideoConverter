from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gvc.models import VideoInfo
from gvc.recommendations import get_engine_recommendation_sections


Translator = Callable[..., str]


@dataclass(frozen=True, slots=True)
class ExperienceContext:
    engine_profile: str
    fmt: str
    quality: str
    resolution: str
    fps: float
    keep_audio: bool
    ogv_mode: str
    output_folder: str
    source_path: str | None
    language_code: str
    keep_original_labels: frozenset[str]


def html_list(items: list[str] | tuple[str, ...]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def preset_summary(ctx: ExperienceContext, tr: Translator) -> tuple[str, str]:
    engine = _engine_key(ctx)
    fmt = _format_key(ctx)
    if fmt != "ogv":
        return tr(f"format_{fmt}_title"), tr(f"format_{fmt}_body")

    mode = ctx.ogv_mode.strip().lower()
    preset_map = {
        "official godot": ("preset_official_godot_title", "preset_official_godot_body"),
        "seek friendly": ("preset_seek_friendly_title", "preset_seek_friendly_body"),
        "ideal loop": ("preset_ideal_loop_title", "preset_ideal_loop_body"),
        "mobile optimized": ("preset_mobile_optimized_title", "preset_mobile_optimized_body"),
        "high compression": ("preset_high_compression_title", "preset_high_compression_body"),
        "love2d compatibility": ("preset_love2d_compatibility_title", "preset_love2d_compatibility_body"),
        "lightweight": ("preset_lightweight_title", "preset_lightweight_body"),
    }
    title_key, body_key = preset_map.get(
        mode,
        (
            f"preset_{engine}_default_title",
            f"preset_{engine}_default_body",
        ),
    )
    return tr(title_key), tr(body_key)


def summary_html(ctx: ExperienceContext, info: VideoInfo | None, tr: Translator) -> str:
    title, _body = preset_summary(ctx, tr)
    source_name = Path(ctx.source_path).name if ctx.source_path else tr("no_file_selected")
    items = [
        f"{tr('summary_engine')}: {ctx.engine_profile}",
        f"{tr('summary_target')}: {ctx.fmt}",
        f"{tr('summary_preset')}: {title}",
        f"{tr('summary_resolution')}: {_resolution_for_summary(ctx, info, tr)}",
        f"{tr('summary_fps')}: {ctx.fps:g}",
        f"{tr('summary_audio')}: {tr('audio_kept') if ctx.keep_audio else tr('audio_removed')}",
        f"{tr('summary_output_file')}: {Path(ctx.output_folder or 'output') / _output_preview_name(ctx)}",
    ]
    return (
        f"<h3>{html.escape(tr('summary_title'))}</h3>"
        f"<p><b>{html.escape(source_name)}</b></p>"
        f"{html_list(items)}"
        f"<p><b>{html.escape(tr('summary_expectation'))}</b> "
        f"{html.escape(summary_expectation(ctx, tr))}</p>"
    )


def guidance_html(ctx: ExperienceContext, info: VideoInfo | None, tr: Translator) -> str:
    title, body = preset_summary(ctx, tr)
    if not info or not getattr(info, "is_valid", False):
        return f"<p>{html.escape(tr('no_recommendations'))}</p>"

    sections = get_engine_recommendation_sections(
        info,
        ctx.engine_profile,
        keep_audio=ctx.keep_audio,
        target_format=ctx.fmt,
        language=ctx.language_code,
    )
    if not sections.what_has and not sections.next_step:
        return f"<p>{html.escape(tr('no_recommendations'))}</p>"

    blocks = [
        f"<h3>{html.escape(tr('guide_source_title'))}</h3>{html_list(sections.what_has)}",
        f"<h3>{html.escape(tr('guide_preset_title', preset=title))}</h3><p>{html.escape(body)}</p>",
        f"<h3>{html.escape(tr('guide_next_title'))}</h3>{html_list(sections.next_step)}",
    ]
    return "".join(blocks)


def summary_expectation(ctx: ExperienceContext, tr: Translator) -> str:
    fmt = _format_key(ctx)
    if fmt == "ogv":
        mode = ctx.ogv_mode.strip().lower()
        if mode == "ideal loop":
            return tr("expect_loop")
        if mode == "seek friendly":
            return tr("expect_seek")
        if mode in {"mobile optimized", "love2d compatibility"}:
            return tr("expect_safe")
        if mode in {"high compression", "lightweight"}:
            return tr("expect_small")
        return tr("expect_engine_default", engine=ctx.engine_profile)
    if fmt == "mp4":
        return tr("expect_mp4")
    if fmt == "webm":
        return tr("expect_webm")
    return tr("expect_gif")


def _engine_key(ctx: ExperienceContext) -> str:
    return "love2d" if ctx.engine_profile.strip().lower() == "love2d" else "godot"


def _format_key(ctx: ExperienceContext) -> str:
    return ctx.fmt.strip().lower()


def _resolution_for_summary(ctx: ExperienceContext, info: VideoInfo | None, tr: Translator) -> str:
    current = ctx.resolution.strip()
    if current and current not in ctx.keep_original_labels:
        return current
    if info and getattr(info, "is_valid", False):
        return f"{info.width}x{info.height}"
    return tr("keep_original")


def _output_preview_name(ctx: ExperienceContext) -> str:
    stem = Path(ctx.source_path).stem if ctx.source_path else "video"
    suffix_map = {"ogv": ".ogv", "mp4": ".mp4", "webm": ".webm", "gif": ".gif"}
    return f"{stem}_converted{suffix_map.get(_format_key(ctx), '.ogv')}"
