from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
from typing import Any


@dataclass(slots=True)
class ProjectMeta:
    id: str
    name: str
    story_prompt: str
    status: str
    media_roots: list[str] = field(default_factory=list)
    analysis_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Asset:
    id: str
    name: str
    source_path: str
    proxy_path: str
    duration_sec: float
    fps: float
    width: int
    height: int
    has_speech: bool
    interchange_reel_name: str
    source_timecode: str = "00:00:00:00"
    has_proxy: bool = True
    proxy_match_confidence: float = 1.0
    proxy_match_reason: str = "Exact source/proxy mapping."


@dataclass(slots=True)
class SegmentEvidence:
    media_path: str
    transcript_excerpt: str
    story_prompt: str
    analysis_mode: str
    keyframe_timestamps_sec: list[float]
    keyframe_paths: list[str]
    context_window_start_sec: float
    context_window_end_sec: float
    metrics_snapshot: dict[str, float]
    transcript_status: str = ""
    speech_mode_source: str = ""
    contact_sheet_path: str = ""
    transcript_turn_count: int = 0
    transcript_turn_ranges_sec: list[list[float]] = field(default_factory=list)
    turn_completeness: float = 0.0
    speech_structure_label: str = ""
    speech_structure_cues: list[str] = field(default_factory=list)
    speech_structure_confidence: float = 0.0


@dataclass(slots=True)
class PrefilterDecision:
    score: float
    shortlisted: bool
    filtered_before_vlm: bool
    selection_reason: str
    sampled_frame_count: int
    sampled_frame_timestamps_sec: list[float]
    top_frame_timestamps_sec: list[float]
    metrics_snapshot: dict[str, float]
    deduplicated: bool = False
    dedup_group_id: int | None = None
    clip_gated: bool = False
    vlm_budget_capped: bool = False
    boundary_strategy: str = "legacy"
    boundary_confidence: float = 0.0
    seed_region_ids: list[str] = field(default_factory=list)
    seed_region_sources: list[str] = field(default_factory=list)
    seed_region_ranges_sec: list[list[float]] = field(default_factory=list)
    assembly_operation: str = "none"
    assembly_rule_family: str = ""
    assembly_source_segment_ids: list[str] = field(default_factory=list)
    assembly_source_ranges_sec: list[list[float]] = field(default_factory=list)
    transcript_turn_ids: list[str] = field(default_factory=list)
    transcript_turn_ranges_sec: list[list[float]] = field(default_factory=list)
    transcript_turn_alignment: str = ""
    speech_structure_label: str = ""
    speech_structure_cues: list[str] = field(default_factory=list)
    speech_structure_confidence: float = 0.0


@dataclass(slots=True)
class SegmentUnderstanding:
    provider: str
    provider_model: str
    schema_version: str
    summary: str
    subjects: list[str]
    actions: list[str]
    shot_type: str
    camera_motion: str
    mood: str
    story_roles: list[str]
    quality_findings: list[str]
    keep_label: str
    confidence: float
    rationale: str
    risk_flags: list[str]
    visual_distinctiveness: float
    clarity: float
    story_relevance: float


@dataclass(slots=True)
class SegmentReviewState:
    shortlisted: bool
    filtered_before_vlm: bool
    clip_scored: bool
    clip_score: float | None = None
    clip_gated: bool = False
    deduplicated: bool = False
    dedup_group_id: int | None = None
    vlm_budget_capped: bool = False
    model_analyzed: bool = False
    deterministic_fallback: bool = False
    evidence_keyframe_count: int = 0
    analysis_path_summary: str = ""
    blocked_reason: str = ""
    boundary_strategy_label: str = ""
    boundary_confidence: float | None = None
    lineage_summary: str = ""
    semantic_validation_status: str = ""
    semantic_validation_summary: str = ""
    transcript_status: str = ""
    transcript_summary: str = ""
    speech_mode_source: str = ""
    turn_summary: str = ""
    speech_structure_summary: str = ""


@dataclass(slots=True)
class BoundaryValidationResult:
    status: str
    decision: str
    reason: str
    confidence: float
    ambiguity_score: float = 0.0
    target_reason: str = ""
    provider: str = ""
    provider_model: str = ""
    skip_reason: str = ""
    applied: bool = False
    original_range_sec: list[float] = field(default_factory=list)
    suggested_range_sec: list[float] = field(default_factory=list)
    split_ranges_sec: list[list[float]] = field(default_factory=list)


@dataclass(slots=True)
class CandidateSegment:
    id: str
    asset_id: str
    start_sec: float
    end_sec: float
    analysis_mode: str
    transcript_excerpt: str
    description: str
    quality_metrics: dict[str, float]
    prefilter: PrefilterDecision | None = None
    evidence_bundle: SegmentEvidence | None = None
    ai_understanding: SegmentUnderstanding | None = None
    review_state: SegmentReviewState | None = None
    boundary_validation: BoundaryValidationResult | None = None


@dataclass(slots=True)
class TakeRecommendation:
    id: str
    candidate_segment_id: str
    title: str
    is_best_take: bool
    selection_reason: str
    score_technical: float
    score_semantic: float
    score_story: float
    score_total: float
    outcome: str = "backup"
    within_asset_rank: int = 0
    score_gap_to_winner: float = 0.0
    score_driver_labels: list[str] = field(default_factory=list)
    limiting_factor_labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TimelineItem:
    id: str
    take_recommendation_id: str
    order_index: int
    trim_in_sec: float
    trim_out_sec: float
    label: str
    notes: str
    source_asset_path: str
    source_reel: str
    sequence_group: str = ""
    sequence_role: str = ""
    sequence_score: float = 0.0
    sequence_rationale: list[str] = field(default_factory=list)
    sequence_driver_labels: list[str] = field(default_factory=list)
    sequence_tradeoff_labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Timeline:
    id: str
    version: int
    story_summary: str
    items: list[TimelineItem]


@dataclass(slots=True)
class ProjectData:
    project: ProjectMeta
    assets: list[Asset]
    candidate_segments: list[CandidateSegment]
    take_recommendations: list[TakeRecommendation]
    timeline: Timeline

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectData":
        project_payload = payload["project"]
        return cls(
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
                CandidateSegment(
                    id=segment["id"],
                    asset_id=segment["asset_id"],
                    start_sec=segment["start_sec"],
                    end_sec=segment["end_sec"],
                    analysis_mode=segment["analysis_mode"],
                    transcript_excerpt=segment.get("transcript_excerpt", ""),
                    description=segment.get("description", ""),
                    quality_metrics=segment.get("quality_metrics", {}),
                    prefilter=(
                        PrefilterDecision(
                            score=segment["prefilter"].get("score", 0.0),
                            shortlisted=segment["prefilter"].get("shortlisted", False),
                            filtered_before_vlm=segment["prefilter"].get("filtered_before_vlm", False),
                            selection_reason=segment["prefilter"].get("selection_reason", ""),
                            sampled_frame_count=segment["prefilter"].get("sampled_frame_count", 0),
                            sampled_frame_timestamps_sec=segment["prefilter"].get("sampled_frame_timestamps_sec", []),
                            top_frame_timestamps_sec=segment["prefilter"].get("top_frame_timestamps_sec", []),
                            metrics_snapshot=segment["prefilter"].get("metrics_snapshot", {}),
                            deduplicated=segment["prefilter"].get("deduplicated", False),
                            dedup_group_id=segment["prefilter"].get("dedup_group_id", None),
                            clip_gated=segment["prefilter"].get("clip_gated", False),
                            vlm_budget_capped=segment["prefilter"].get("vlm_budget_capped", False),
                            boundary_strategy=segment["prefilter"].get("boundary_strategy", "legacy"),
                            boundary_confidence=segment["prefilter"].get("boundary_confidence", 0.0),
                            seed_region_ids=segment["prefilter"].get("seed_region_ids", []),
                            seed_region_sources=segment["prefilter"].get("seed_region_sources", []),
                            seed_region_ranges_sec=segment["prefilter"].get("seed_region_ranges_sec", []),
                            assembly_operation=segment["prefilter"].get("assembly_operation", "none"),
                            assembly_rule_family=segment["prefilter"].get("assembly_rule_family", ""),
                            assembly_source_segment_ids=segment["prefilter"].get("assembly_source_segment_ids", []),
                            assembly_source_ranges_sec=segment["prefilter"].get("assembly_source_ranges_sec", []),
                            transcript_turn_ids=segment["prefilter"].get("transcript_turn_ids", []),
                            transcript_turn_ranges_sec=segment["prefilter"].get("transcript_turn_ranges_sec", []),
                            transcript_turn_alignment=segment["prefilter"].get("transcript_turn_alignment", ""),
                            speech_structure_label=segment["prefilter"].get("speech_structure_label", ""),
                            speech_structure_cues=segment["prefilter"].get("speech_structure_cues", []),
                            speech_structure_confidence=segment["prefilter"].get("speech_structure_confidence", 0.0),
                        )
                        if segment.get("prefilter") is not None
                        else None
                    ),
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

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ProjectData":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
