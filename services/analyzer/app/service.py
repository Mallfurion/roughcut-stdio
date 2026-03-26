from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from .analysis import build_project_from_media_roots, build_segment_review_state, build_take_recommendations, inspect_runtime_capabilities
from .domain import Asset, ProjectData, TakeRecommendation
from .fcpxml import export_fcpxml


def load_project(path: str | Path) -> ProjectData:
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

    return replace(project_data, take_recommendations=rescored_takes)


def export_project_fcpxml(path: str | Path) -> str:
    return export_fcpxml(load_project(path))


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
