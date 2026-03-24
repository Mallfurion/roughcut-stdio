from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from .analysis import build_project_from_media_roots, inspect_runtime_capabilities
from .domain import Asset, ProjectData, TakeRecommendation
from .fcpxml import export_fcpxml
from .scoring import score_segment


def load_project(path: str | Path) -> ProjectData:
    project_data = ProjectData.from_json_file(path)
    segment_by_id = {segment.id: segment for segment in project_data.candidate_segments}
    asset_by_id = {asset.id: asset for asset in project_data.assets}

    rescored_takes: list[TakeRecommendation] = []
    for take in project_data.take_recommendations:
        segment = segment_by_id[take.candidate_segment_id]
        asset = asset_by_id[segment.asset_id]
        breakdown = score_segment(asset, segment)
        rescored_takes.append(
            replace(
                take,
                score_technical=breakdown.technical,
                score_semantic=breakdown.semantic,
                score_story=breakdown.story,
                score_total=breakdown.total,
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
