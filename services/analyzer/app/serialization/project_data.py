from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ..domain import (
    Asset,
    BoundaryValidationResult,
    CandidateSegment,
    PrefilterDecision,
    ProjectData,
    ProjectMeta,
    SegmentEvidence,
    SegmentReviewState,
    SegmentUnderstanding,
    TakeRecommendation,
    Timeline,
    TimelineItem,
)


def project_data_from_dict(payload: dict[str, Any]) -> ProjectData:
    project_payload = payload["project"]
    return ProjectData(
        project=ProjectMeta(
            id=project_payload["id"],
            name=project_payload["name"],
            story_prompt=project_payload.get("story_prompt", ""),
            status=project_payload.get("status", "draft"),
            media_roots=project_payload.get("media_roots", []),
            analysis_summary=project_payload.get("analysis_summary", {}),
        ),
        assets=[Asset(**asset) for asset in payload["assets"]],
        candidate_segments=[
            _candidate_segment_from_dict(segment)
            for segment in payload["candidate_segments"]
        ],
        take_recommendations=[
            TakeRecommendation(**take) for take in payload["take_recommendations"]
        ],
        timeline=Timeline(
            id=payload["timeline"]["id"],
            version=payload["timeline"]["version"],
            story_summary=payload["timeline"]["story_summary"],
            items=[TimelineItem(**item) for item in payload["timeline"]["items"]],
        ),
    )


def project_data_from_json_file(path: str | Path) -> ProjectData:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return project_data_from_dict(payload)


def project_data_to_dict(project_data: ProjectData) -> dict[str, Any]:
    return asdict(project_data)


def _candidate_segment_from_dict(segment: dict[str, Any]) -> CandidateSegment:
    return CandidateSegment(
        id=segment["id"],
        asset_id=segment["asset_id"],
        start_sec=segment["start_sec"],
        end_sec=segment["end_sec"],
        analysis_mode=segment["analysis_mode"],
        transcript_excerpt=segment.get("transcript_excerpt", ""),
        description=segment.get("description", ""),
        quality_metrics=segment.get("quality_metrics", {}),
        prefilter=_prefilter_from_dict(segment.get("prefilter")),
        evidence_bundle=(
            SegmentEvidence(**segment["evidence_bundle"])
            if segment.get("evidence_bundle") is not None
            else None
        ),
        ai_understanding=(
            SegmentUnderstanding(**segment["ai_understanding"])
            if segment.get("ai_understanding") is not None
            else None
        ),
        review_state=(
            SegmentReviewState(**segment["review_state"])
            if segment.get("review_state") is not None
            else None
        ),
        boundary_validation=(
            BoundaryValidationResult(**segment["boundary_validation"])
            if segment.get("boundary_validation") is not None
            else None
        ),
    )


def _prefilter_from_dict(payload: dict[str, Any] | None) -> PrefilterDecision | None:
    if payload is None:
        return None
    return PrefilterDecision(
        score=payload.get("score", 0.0),
        shortlisted=payload.get("shortlisted", False),
        filtered_before_vlm=payload.get("filtered_before_vlm", False),
        selection_reason=payload.get("selection_reason", ""),
        sampled_frame_count=payload.get("sampled_frame_count", 0),
        sampled_frame_timestamps_sec=payload.get("sampled_frame_timestamps_sec", []),
        top_frame_timestamps_sec=payload.get("top_frame_timestamps_sec", []),
        metrics_snapshot=payload.get("metrics_snapshot", {}),
        deduplicated=payload.get("deduplicated", False),
        dedup_group_id=payload.get("dedup_group_id", None),
        clip_gated=payload.get("clip_gated", False),
        vlm_budget_capped=payload.get("vlm_budget_capped", False),
        boundary_strategy=payload.get("boundary_strategy", "legacy"),
        boundary_confidence=payload.get("boundary_confidence", 0.0),
        seed_region_ids=payload.get("seed_region_ids", []),
        seed_region_sources=payload.get("seed_region_sources", []),
        seed_region_ranges_sec=payload.get("seed_region_ranges_sec", []),
        assembly_operation=payload.get("assembly_operation", "none"),
        assembly_rule_family=payload.get("assembly_rule_family", ""),
        assembly_source_segment_ids=payload.get("assembly_source_segment_ids", []),
        assembly_source_ranges_sec=payload.get("assembly_source_ranges_sec", []),
        transcript_turn_ids=payload.get("transcript_turn_ids", []),
        transcript_turn_ranges_sec=payload.get("transcript_turn_ranges_sec", []),
        transcript_turn_alignment=payload.get("transcript_turn_alignment", ""),
        speech_structure_label=payload.get("speech_structure_label", ""),
        speech_structure_cues=payload.get("speech_structure_cues", []),
        speech_structure_confidence=payload.get("speech_structure_confidence", 0.0),
    )
