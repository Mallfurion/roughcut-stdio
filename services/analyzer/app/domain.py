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
    contact_sheet_path: str = ""


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
                        PrefilterDecision(**segment["prefilter"])
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
