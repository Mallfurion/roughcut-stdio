from __future__ import annotations

from dataclasses import dataclass

from .domain import Asset, CandidateSegment


@dataclass(slots=True)
class ScoreBreakdown:
    analysis_mode: str
    technical: float
    semantic: float
    story: float
    total: float


def score_segment(asset: Asset, segment: CandidateSegment) -> ScoreBreakdown:
    metrics = segment.quality_metrics
    analysis_mode = "speech" if asset.has_speech and segment.transcript_excerpt.strip() else "visual"

    technical = weighted_average(
        {
            "sharpness": metrics.get("sharpness", 0.0),
            "stability": metrics.get("stability", 0.0),
            "duration_fit": metrics.get("duration_fit", 0.0),
            "subject_clarity": metrics.get("subject_clarity", 0.0),
            "audio_energy": metrics.get("audio_energy", 0.0) if analysis_mode == "speech" else 0.0,
            "motion_energy": metrics.get("motion_energy", 0.0) if analysis_mode == "visual" else 0.0,
        },
        {
            "sharpness": 0.22,
            "stability": 0.18,
            "duration_fit": 0.2,
            "subject_clarity": 0.18,
            "audio_energy": 0.22,
            "motion_energy": 0.22,
        },
    )

    if analysis_mode == "speech":
        semantic_values = {
            "hook_strength": metrics.get("hook_strength", 0.0),
            "story_alignment": metrics.get("story_alignment", 0.0),
            "speech_ratio": metrics.get("speech_ratio", 0.0),
            "subject_clarity": metrics.get("subject_clarity", 0.0),
        }
        semantic_weights = {
            "hook_strength": 0.32,
            "story_alignment": 0.28,
            "speech_ratio": 0.24,
            "subject_clarity": 0.16,
        }

        # Include CLIP score if available
        if segment.prefilter and "clip_score" in segment.prefilter.metrics_snapshot:
            semantic_values["clip_score"] = segment.prefilter.metrics_snapshot["clip_score"]
            semantic_weights["clip_score"] = 0.12

        semantic = weighted_average(semantic_values, semantic_weights)
        story = weighted_average(
            {
                "story_alignment": metrics.get("story_alignment", 0.0),
                "hook_strength": metrics.get("hook_strength", 0.0),
                "duration_fit": metrics.get("duration_fit", 0.0),
            },
            {
                "story_alignment": 0.46,
                "hook_strength": 0.28,
                "duration_fit": 0.26,
            },
        )
    else:
        semantic_values = {
            "visual_novelty": metrics.get("visual_novelty", 0.0),
            "subject_clarity": metrics.get("subject_clarity", 0.0),
            "motion_energy": metrics.get("motion_energy", 0.0),
            "hook_strength": metrics.get("hook_strength", 0.0),
        }
        semantic_weights = {
            "visual_novelty": 0.34,
            "subject_clarity": 0.18,
            "motion_energy": 0.24,
            "hook_strength": 0.24,
        }

        # Include CLIP score if available
        if segment.prefilter and "clip_score" in segment.prefilter.metrics_snapshot:
            semantic_values["clip_score"] = segment.prefilter.metrics_snapshot["clip_score"]
            semantic_weights["clip_score"] = 0.15

        semantic = weighted_average(semantic_values, semantic_weights)
        story = weighted_average(
            {
                "story_alignment": metrics.get("story_alignment", 0.0),
                "visual_novelty": metrics.get("visual_novelty", 0.0),
                "duration_fit": metrics.get("duration_fit", 0.0),
                "motion_energy": metrics.get("motion_energy", 0.0),
            },
            {
                "story_alignment": 0.38,
                "visual_novelty": 0.28,
                "duration_fit": 0.2,
                "motion_energy": 0.14,
            },
        )

    total = clamp((technical * 0.35) + (semantic * 0.4) + (story * 0.25))

    return ScoreBreakdown(
        analysis_mode=analysis_mode,
        technical=round(technical, 4),
        semantic=round(semantic, 4),
        story=round(story, 4),
        total=round(total, 4),
    )


def weighted_average(values: dict[str, float], weights: dict[str, float]) -> float:
    numerator = 0.0
    denominator = 0.0

    for key, value in values.items():
        weight = weights.get(key, 0.0)
        numerator += clamp(value) * weight
        denominator += weight

    if denominator == 0:
        return 0.0

    return numerator / denominator


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))

