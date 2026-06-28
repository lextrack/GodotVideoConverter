from __future__ import annotations

import os
import re
import string
import sys

from gvc.i18n_catalogs import (
    DEFAULT_LANGUAGE_LABEL,
    LANGUAGE_CODES,
    LANGUAGE_LABELS,
    REQUIRED_UI_KEYS,
    UI_TEXT,
)
from gvc.recommendation_catalogs import RECOMMENDATION_PROFILES

_REPORTED_MISSING: set[tuple[str, str]] = set()
_REPORTED_FORMAT_ERRORS: set[tuple[str, str]] = set()
_SUSPICIOUS_TEXT_MARKERS = ("Ã", "Â", "â", "\ufffd")


def normalize_language_label(language: str) -> str:
    if language in UI_TEXT:
        return language
    normalized = (language or "").strip()
    aliases = {
        "english": "English",
        "en": "English",
        "español": "Español",
        "espanol": "Español",
        "es": "Español",
        "français": "Français",
        "francais": "Français",
        "fr": "Français",
        "deutsch": "Deutsch",
        "de": "Deutsch",
        "简体中文": "简体中文",
        "中文": "简体中文",
        "zh": "简体中文",
        "zh_cn": "简体中文",
        "zh-cn": "简体中文",
        "zh_hans": "简体中文",
        "zh-hans": "简体中文",
    }
    return aliases.get(normalized.casefold(), DEFAULT_LANGUAGE_LABEL)


def language_label_to_code(language: str) -> str:
    label = normalize_language_label(language)
    return LANGUAGE_CODES.get(label, "en")


def _extract_placeholders(text: str) -> set[str]:
    placeholders: set[str] = set()
    for _, field_name, _, _ in string.Formatter().parse(text):
        if field_name:
            placeholders.add(field_name)
    return placeholders


def _find_placeholder_issues() -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    default_table = UI_TEXT[DEFAULT_LANGUAGE_LABEL]
    for label, table in UI_TEXT.items():
        if label == DEFAULT_LANGUAGE_LABEL:
            continue
        mismatches: list[str] = []
        for key in REQUIRED_UI_KEYS:
            default_text = default_table[key]
            localized_text = table.get(key)
            if localized_text is None:
                continue
            default_fields = _extract_placeholders(default_text)
            localized_fields = _extract_placeholders(localized_text)
            if default_fields != localized_fields:
                mismatches.append(
                    f"{key} -> placeholders {sorted(localized_fields)} expected {sorted(default_fields)}"
                )
        if mismatches:
            issues[label] = mismatches
    return issues


def _find_suspicious_catalog_text() -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    for label, table in UI_TEXT.items():
        suspicious: list[str] = []
        for key, value in table.items():
            if any(marker in value for marker in _SUSPICIOUS_TEXT_MARKERS):
                suspicious.append(f"{key} -> {value}")
        if suspicious:
            issues[label] = suspicious
    return issues


def validate_ui_catalog() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    missing: dict[str, list[str]] = {}
    extra: dict[str, list[str]] = {}
    for label, table in UI_TEXT.items():
        keys = set(table.keys())
        missing_keys = sorted(REQUIRED_UI_KEYS - keys)
        if missing_keys:
            missing[label] = missing_keys
        extra_keys = sorted(keys - REQUIRED_UI_KEYS)
        if extra_keys:
            extra[label] = extra_keys
    return missing, extra


def _report_catalog_issues_once() -> None:
    missing, extra = validate_ui_catalog()
    placeholder_issues = _find_placeholder_issues()
    suspicious_text = _find_suspicious_catalog_text()
    if not missing and not extra and not placeholder_issues and not suspicious_text:
        return

    lines = ["[gvc.i18n] Translation catalog issues detected:"]
    for label, keys in missing.items():
        lines.append(f"  - {label}: missing keys -> {', '.join(keys)}")
    for label, keys in extra.items():
        lines.append(f"  - {label}: extra keys -> {', '.join(keys)}")
    for label, entries in placeholder_issues.items():
        lines.append(f"  - {label}: placeholder mismatches -> {'; '.join(entries)}")
    for label, entries in suspicious_text.items():
        lines.append(f"  - {label}: suspicious text -> {'; '.join(entries)}")
    message = "\n".join(lines)

    if os.getenv("GVC_I18N_STRICT", "").lower() in {"1", "true", "yes"}:
        raise KeyError(message)

    if os.getenv("GVC_I18N_WARN", "1").lower() not in {"0", "false", "no"}:
        print(message, file=sys.stderr)


def ui_text(language: str, key: str, **kwargs) -> str:
    label = normalize_language_label(language)
    default_table = UI_TEXT[DEFAULT_LANGUAGE_LABEL]
    localized_table = UI_TEXT[label]

    if key not in default_table:
        text = f"[missing-default:{key}]"
    elif key in localized_table:
        text = localized_table[key]
    else:
        text = default_table[key]
        report_key = (label, key)
        if report_key not in _REPORTED_MISSING:
            _REPORTED_MISSING.add(report_key)
            if os.getenv("GVC_I18N_WARN", "1").lower() not in {"0", "false", "no"}:
                print(
                    f"[gvc.i18n] Missing translation key '{key}' for language '{label}', using English fallback.",
                    file=sys.stderr,
                )
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (IndexError, KeyError, ValueError) as exc:
        report_key = (label, key)
        if report_key not in _REPORTED_FORMAT_ERRORS:
            _REPORTED_FORMAT_ERRORS.add(report_key)
            if os.getenv("GVC_I18N_WARN", "1").lower() not in {"0", "false", "no"}:
                print(
                    f"[gvc.i18n] Format error for key '{key}' in language '{label}': {exc}.",
                    file=sys.stderr,
                )
        fallback_text = default_table.get(key, text)
        try:
            return fallback_text.format(**kwargs)
        except (IndexError, KeyError, ValueError):
            return fallback_text


def translate_runtime_error(message: str, language: str) -> str:
    text = (message or "").strip()
    if not text:
        return ""

    match = re.fullmatch(
        r"Atlas too large \(([^)]+)\)\. Reduce frames, duration, or frame size\.",
        text,
    )
    if match:
        return ui_text(language, "error_atlas_too_large", size=match.group(1))

    match = re.fullmatch(r"Atlas too large \(([^)]+)\)\. Reduce FPS\.", text)
    if match:
        return ui_text(language, "error_atlas_too_large", size=match.group(1))

    match = re.fullmatch(r"Input file not found: (.+)", text)
    if match:
        return ui_text(language, "error_input_file_not_found", name=match.group(1))

    if text == "video fps must be between 1 and 60":
        return ui_text(language, "error_video_fps_range")

    if text == "atlas fps must be between 1 and 30":
        return ui_text(language, "error_atlas_fps_range")

    if text == "atlas start time must be before the end of the video":
        return ui_text(language, "error_atlas_start_range")

    if text == "output resolution must use WIDTHxHEIGHT, for example 1280x720":
        return ui_text(language, "error_resolution_format")

    if text == "invalid video file":
        return ui_text(language, "error_invalid_video_file_runtime")

    match = re.fullmatch(r"FFmpeg failed: (.+)", text)
    if match:
        return ui_text(language, "error_ffmpeg_failed", detail=match.group(1))

    return text


def translate_recommendations(text: str, language: str) -> str:
    profile = RECOMMENDATION_PROFILES.get(language_label_to_code(language))
    if profile is None:
        return text

    out = text
    for source, replacement in profile.replacements.items():
        out = out.replace(source, replacement)
    for pattern, replacement in profile.regex_rules:
        out = re.sub(pattern, replacement, out)
    return out


_report_catalog_issues_once()
