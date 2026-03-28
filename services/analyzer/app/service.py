from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Callable

from .analysis import (
    build_project_from_media_roots,
    build_segment_review_state,
    build_take_recommendations,
    build_timeline,
    inspect_runtime_capabilities,
)
from .domain import Asset, ProjectData, TakeRecommendation
from .fcpxml import export_fcpxml

CLEAR_BEST_TAKE_SENTINEL = "__roughcut_clear_best_take__"

__all__ = [
    "CLEAR_BEST_TAKE_SENTINEL",
    "apply_best_take_overrides",
    "export_project_fcpxml",
    "export_project_fcpxml_with_override_file",
    "load_project",
    "load_project_with_override_file",
    "read_best_take_overrides",
    "runtime_capabilities",
    "scan_and_analyze_media_root",
]


def load_project(
    path: str | Path,
    *,
    best_take_overrides: dict[str, str] | None = None,
) -> ProjectData:
    project_data = ProjectData.from_json_file(path)
    computed_takes = build_take_recommendations(project_data.assets, project_data.candidate_segments)
    computed_by_segment_id = {take.candidate_segment_id: take for take in computed_takes}

    for segment in project_data.candidate_segments:
        segment.review_state = build_segment_review_state(segment)

    rescored_takes: list[TakeRecommendation] = []
    for take in project_data.take_recommendations:
        computed_take = computed_by_segment_id.get(take.candidate_segment_id)
        if computed_take is None:
            rescored_takes.append(take)
            continue
        rescored_takes.append(
            replace(
                take,
                candidate_segment_id=computed_take.candidate_segment_id,
                is_best_take=computed_take.is_best_take,
                baseline_is_best_take=computed_take.is_best_take,
                editor_override=False,
                editor_cleared=False,
                selection_reason=computed_take.selection_reason,
                score_technical=computed_take.score_technical,
                score_semantic=computed_take.score_semantic,
                score_story=computed_take.score_story,
                score_total=computed_take.score_total,
                outcome=computed_take.outcome,
                within_asset_rank=computed_take.within_asset_rank,
                score_gap_to_winner=computed_take.score_gap_to_winner,
                score_driver_labels=list(computed_take.score_driver_labels),
                limiting_factor_labels=list(computed_take.limiting_factor_labels),
            )
        )

    resolved_project = replace(project_data, take_recommendations=rescored_takes)
    if not best_take_overrides:
        return resolved_project
    return apply_best_take_overrides(resolved_project, best_take_overrides)


def load_project_with_override_file(
    path: str | Path,
    override_path: str | Path | None = None,
) -> ProjectData:
    return load_project(path, best_take_overrides=read_best_take_overrides(path, override_path))


def export_project_fcpxml(
    path: str | Path,
    *,
    best_take_overrides: dict[str, str] | None = None,
) -> str:
    return export_fcpxml(load_project(path, best_take_overrides=best_take_overrides))


def export_project_fcpxml_with_override_file(
    path: str | Path,
    override_path: str | Path | None = None,
) -> str:
    return export_project_fcpxml(path, best_take_overrides=read_best_take_overrides(path, override_path))


def scan_and_analyze_media_root(
    *,
    project_name: str,
    media_roots: list[str],
    story_prompt: str,
    artifacts_root: str | Path | None = None,
    status_callback: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, int, Asset], None] | None = None,
) -> ProjectData:
    return build_project_from_media_roots(
        project_name=project_name,
        media_roots=media_roots,
        story_prompt=story_prompt,
        artifacts_root=artifacts_root,
        status_callback=status_callback,
        progress_callback=progress_callback,
    )


def runtime_capabilities() -> dict[str, bool]:
    return inspect_runtime_capabilities()


def apply_best_take_overrides(project_data: ProjectData, overrides_by_asset: dict[str, str]) -> ProjectData:
    if not overrides_by_asset:
        return project_data

    segment_by_id = {segment.id: segment for segment in project_data.candidate_segments}
    asset_ids = {asset.id for asset in project_data.assets}
    normalized_overrides: dict[str, str] = {}
    cleared_asset_ids: set[str] = set()
    for asset_id, segment_id in overrides_by_asset.items():
        if asset_id not in asset_ids:
            continue
        if segment_id == CLEAR_BEST_TAKE_SENTINEL:
            cleared_asset_ids.add(asset_id)
            continue
        segment = segment_by_id.get(segment_id)
        if segment is None or segment.asset_id != asset_id:
            continue
        normalized_overrides[asset_id] = segment_id

    if not normalized_overrides and not cleared_asset_ids:
        return project_data

    resolved_takes: list[TakeRecommendation] = []
    for take in project_data.take_recommendations:
        segment = segment_by_id.get(take.candidate_segment_id)
        if segment is None:
            resolved_takes.append(take)
            continue

        override_segment_id = normalized_overrides.get(segment.asset_id)
        baseline_is_best_take = take.is_best_take
        if segment.asset_id in cleared_asset_ids:
            was_selected = take.is_best_take
            cleared_reason = take.selection_reason
            if baseline_is_best_take:
                cleared_reason = (
                    f"Editor cleared this clip from the timeline. "
                    f"Analyzer originally selected it at {round(take.score_total * 100):d}/100."
                )
            elif take.editor_override or was_selected:
                cleared_reason = (
                    f"Editor cleared this clip from the timeline after selecting this take at "
                    f"{round(take.score_total * 100):d}/100."
                )
            resolved_takes.append(
                replace(
                    take,
                    is_best_take=False,
                    baseline_is_best_take=baseline_is_best_take,
                    editor_override=False,
                    editor_cleared=was_selected or baseline_is_best_take,
                    outcome="backup" if take.outcome == "best" else take.outcome,
                    selection_reason=cleared_reason,
                )
            )
            continue
        if override_segment_id is None:
            resolved_takes.append(
                replace(
                    take,
                    baseline_is_best_take=baseline_is_best_take,
                    editor_override=False,
                    editor_cleared=False,
                )
            )
            continue

        if take.candidate_segment_id == override_segment_id:
            resolved_takes.append(
                replace(
                    take,
                    is_best_take=True,
                    baseline_is_best_take=baseline_is_best_take,
                    editor_override=True,
                    editor_cleared=False,
                    outcome="best",
                    selection_reason=(
                        f"Editor override selected this take for {segment.asset_id}. "
                        f"Analyzer score remains {round(take.score_total * 100):d}/100."
                    ),
                )
            )
            continue

        replacement_reason = take.selection_reason
        if baseline_is_best_take:
            replacement_reason = (
                f"Analyzer originally selected this take at {round(take.score_total * 100):d}/100, "
                "but a desktop override replaced it for this clip."
            )
        resolved_takes.append(
            replace(
                take,
                is_best_take=False,
                baseline_is_best_take=baseline_is_best_take,
                editor_override=False,
                editor_cleared=False,
                outcome="backup" if take.outcome == "best" else take.outcome,
                selection_reason=replacement_reason,
            )
        )

    timeline = build_timeline(
        resolved_takes,
        project_data.candidate_segments,
        project_data.assets,
        story_prompt=project_data.project.story_prompt,
    )
    return replace(project_data, take_recommendations=resolved_takes, timeline=timeline)


def read_best_take_overrides(
    project_path: str | Path,
    override_path: str | Path | None = None,
) -> dict[str, str]:
    if override_path is None:
        return {}

    override_file = Path(override_path)
    if not override_file.exists():
        return {}

    try:
        payload = json.loads(override_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    project_data = ProjectData.from_json_file(project_path)
    expected_project_id = project_data.project.id
    candidate_segment_ids = sorted(segment.id for segment in project_data.candidate_segments)
    if payload.get("project_id") != expected_project_id:
        return {}
    if sorted(payload.get("candidate_segment_ids", [])) != candidate_segment_ids:
        return {}

    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        return {}
    return {
        str(asset_id): str(segment_id)
        for asset_id, segment_id in overrides.items()
        if isinstance(asset_id, str) and isinstance(segment_id, str)
    }
