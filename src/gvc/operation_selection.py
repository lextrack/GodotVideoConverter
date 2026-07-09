from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

from gvc.file_selection import AUDIO_EXTENSIONS


class OperationKind(StrEnum):
    CONVERT_VIDEO = "convert_video"
    CONVERT_AUDIO = "convert_audio"
    GENERATE_ATLAS = "generate_atlas"


class MediaKind(StrEnum):
    VIDEO = "video"
    AUDIO_ONLY = "audio_only"
    INVALID = "invalid"


class SelectionScope(StrEnum):
    SELECTED = "selected"
    ALL_COMPATIBLE = "all_compatible"


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    source: str
    operation: OperationKind
    allowed: bool
    media_kind: MediaKind
    reason: str | None = None


ProbeFn = Callable[[str], object]
ChooseScopeFn = Callable[[int, int], str | None]


def operation_for_tab_index(index: int) -> OperationKind:
    if index == 1:
        return OperationKind.CONVERT_AUDIO
    if index == 2:
        return OperationKind.GENERATE_ATLAS
    return OperationKind.CONVERT_VIDEO


def evaluate_source_for_operation(src: str, operation: OperationKind, *, probe: ProbeFn) -> EligibilityResult:
    media_kind = detect_media_kind(src, probe=probe)

    if operation == OperationKind.CONVERT_AUDIO:
        if media_kind == MediaKind.AUDIO_ONLY:
            return EligibilityResult(src, operation, True, media_kind)
        try:
            info = probe(src)
        except Exception:
            return EligibilityResult(src, operation, False, MediaKind.INVALID, "probe_failed")
        if bool(getattr(info, "is_valid", False) and getattr(info, "has_audio", False)):
            return EligibilityResult(src, operation, True, MediaKind.VIDEO)
        return EligibilityResult(src, operation, False, media_kind, "audio_export_requires_audio")

    if media_kind == MediaKind.VIDEO:
        return EligibilityResult(src, operation, True, media_kind)
    if media_kind == MediaKind.AUDIO_ONLY:
        return EligibilityResult(src, operation, False, media_kind, "operation_requires_video")
    return EligibilityResult(src, operation, False, media_kind, "invalid_video")


def detect_media_kind(src: str, *, probe: ProbeFn) -> MediaKind:
    if Path(src).suffix.lower() in AUDIO_EXTENSIONS:
        return MediaKind.AUDIO_ONLY
    try:
        info = probe(src)
    except Exception:
        return MediaKind.INVALID
    if bool(getattr(info, "has_audio", False) and getattr(info, "width", 0) <= 0 and getattr(info, "height", 0) <= 0):
        return MediaKind.AUDIO_ONLY
    if bool(getattr(info, "is_valid", False)):
        return MediaKind.VIDEO
    return MediaKind.INVALID


def eligible_inputs_for_operation(paths: list[str], operation: OperationKind, *, probe: ProbeFn) -> list[str]:
    return [
        result.source
        for result in (evaluate_source_for_operation(src, operation, probe=probe) for src in paths)
        if result.allowed
    ]


def evaluate_sources_for_operation(paths: list[str], operation: OperationKind, *, probe: ProbeFn) -> list[EligibilityResult]:
    return [evaluate_source_for_operation(src, operation, probe=probe) for src in paths]


def summarize_ineligible_results(results: list[EligibilityResult]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for result in results:
        if result.allowed or not result.reason:
            continue
        counts[result.reason] = counts.get(result.reason, 0) + 1
    ordered_reasons = [
        "operation_requires_video",
        "audio_export_requires_audio",
        "invalid_video",
        "probe_failed",
    ]
    summary = [(reason, counts[reason]) for reason in ordered_reasons if reason in counts]
    extras = sorted(reason for reason in counts if reason not in ordered_reasons)
    summary.extend((reason, counts[reason]) for reason in extras)
    return summary


def resolve_operation_inputs(
    all_paths: list[str],
    selected_paths: list[str],
    operation: OperationKind,
    *,
    probe: ProbeFn,
    choose_scope: ChooseScopeFn | None = None,
) -> list[str] | None:
    all_inputs = eligible_inputs_for_operation(all_paths, operation, probe=probe)
    if not all_inputs:
        return []

    selected_inputs = eligible_inputs_for_operation(selected_paths, operation, probe=probe)
    if len(all_inputs) <= 1:
        return selected_inputs or all_inputs
    if selected_inputs and set(selected_inputs) == set(all_inputs):
        return all_inputs
    if not selected_inputs:
        return all_inputs
    if choose_scope is None:
        return selected_inputs

    scope = choose_scope(len(selected_inputs), len(all_inputs))
    if scope is None:
        return None
    return selected_inputs if scope == SelectionScope.SELECTED.value else all_inputs
