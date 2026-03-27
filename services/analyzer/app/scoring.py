from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .domain import Asset, CandidateSegment


@dataclass(slots=True)
class ScoreBreakdown:
    analysis_mode: str
    technical: float
    semantic: float
    story: float
    total: float


@dataclass(slots=True)
class ScoreComponentInputs:
    values: dict[str, float]
    weights: dict[str, float]
    blend_weight: float


COMPONENT_BLEND_WEIGHTS = {
    "technical": 0.35,
    "semantic": 0.4,
    "story": 0.25,
}

DRIVER_LABELS = {
    "audio_energy": "audio energy",
    "clip_score": "CLIP semantic match",
    "duration_fit": "duration fit",
    "hook_strength": "hook strength",
    "motion_energy": "motion energy",
    "sharpness": "sharpness",
    "question_answer_flow": "question/answer flow",
    "speech_ratio": "speech ratio",
    "spoken_beat_completeness": "spoken beat completeness",
    "stability": "stability",
    "story_alignment": "story alignment",
    "subject_clarity": "subject clarity",
    "turn_completeness": "turn completeness",
    "visual_novelty": "visual novelty",
    "monologue_continuity": "monologue continuity",
}

SPEECH_FALLBACK_MIN_SPEECH_RATIO = 0.65
SPEECH_FALLBACK_MIN_AUDIO_ENERGY = 0.2
SPEECH_FALLBACK_STRONG_SPEECH_RATIO = 0.9


def infer_analysis_mode(
    asset: Asset,
    transcript_excerpt: str,
    metrics: dict[str, float],
) -> tuple[str, str]:
    if not asset.has_speech:
        return "visual", "not-applicable"

    if transcript_excerpt.strip():
        return "speech", "transcript"

    speech_ratio = clamp(metrics.get("speech_ratio", 0.0))
    audio_energy = clamp(metrics.get("audio_energy", 0.0))
    if (
        speech_ratio >= SPEECH_FALLBACK_STRONG_SPEECH_RATIO
        or (speech_ratio >= SPEECH_FALLBACK_MIN_SPEECH_RATIO and audio_energy >= SPEECH_FALLBACK_MIN_AUDIO_ENERGY)
    ):
        return "speech", "speech-signal-fallback"

    return "visual", "visual"


def score_segment(asset: Asset, segment: CandidateSegment) -> ScoreBreakdown:
    analysis_mode, components = score_component_inputs(asset, segment)
    technical = weighted_average(
        values=components["technical"].values,
        weights=components["technical"].weights,
    )
    semantic = weighted_average(
        values=components["semantic"].values,
        weights=components["semantic"].weights,
    )
    story = weighted_average(
        values=components["story"].values,
        weights=components["story"].weights,
    )
    total = clamp(
        (technical * COMPONENT_BLEND_WEIGHTS["technical"])
        + (semantic * COMPONENT_BLEND_WEIGHTS["semantic"])
        + (story * COMPONENT_BLEND_WEIGHTS["story"])
    )

    return ScoreBreakdown(
        analysis_mode=analysis_mode,
        technical=round(technical, 4),
        semantic=round(semantic, 4),
        story=round(story, 4),
        total=round(total, 4),
    )


def score_component_inputs(asset: Asset, segment: CandidateSegment) -> tuple[str, dict[str, ScoreComponentInputs]]:
    metrics = segment.quality_metrics
    analysis_mode, _analysis_mode_source = infer_analysis_mode(asset, segment.transcript_excerpt, metrics)
    turn_completeness = metrics.get(
        "turn_completeness",
        0.75 if segment.transcript_excerpt.strip() else 0.0,
    )
    spoken_beat_completeness = metrics.get(
        "spoken_beat_completeness",
        turn_completeness,
    )
    question_answer_flow = metrics.get("question_answer_flow", 0.0)
    monologue_continuity = metrics.get("monologue_continuity", 0.0)

    technical_values = {
        "sharpness": metrics.get("sharpness", 0.0),
        "stability": metrics.get("stability", 0.0),
        "duration_fit": metrics.get("duration_fit", 0.0),
        "subject_clarity": metrics.get("subject_clarity", 0.0),
        "audio_energy": metrics.get("audio_energy", 0.0) if analysis_mode == "speech" else 0.0,
        "motion_energy": metrics.get("motion_energy", 0.0) if analysis_mode == "visual" else 0.0,
    }
    technical_weights = {
        "sharpness": 0.22,
        "stability": 0.18,
        "duration_fit": 0.2,
        "subject_clarity": 0.18,
        "audio_energy": 0.22,
        "motion_energy": 0.22,
    }

    if analysis_mode == "speech":
        semantic_values = {
            "hook_strength": metrics.get("hook_strength", 0.0),
            "story_alignment": metrics.get("story_alignment", 0.0),
            "speech_ratio": metrics.get("speech_ratio", 0.0),
            "subject_clarity": metrics.get("subject_clarity", 0.0),
            "turn_completeness": turn_completeness,
        }
        semantic_weights = {
            "hook_strength": 0.22,
            "story_alignment": 0.2,
            "speech_ratio": 0.16,
            "subject_clarity": 0.12,
            "turn_completeness": 0.14,
        }
        if question_answer_flow > 0.0:
            semantic_values["question_answer_flow"] = question_answer_flow
            semantic_weights["question_answer_flow"] = 0.1
            semantic_weights["hook_strength"] = 0.18
            semantic_weights["story_alignment"] = 0.18
        if monologue_continuity > 0.0:
            semantic_values["monologue_continuity"] = monologue_continuity
            semantic_weights["monologue_continuity"] = 0.06
            semantic_weights["speech_ratio"] = 0.13
            semantic_weights["subject_clarity"] = 0.1
        story_values = {
            "story_alignment": metrics.get("story_alignment", 0.0),
            "hook_strength": metrics.get("hook_strength", 0.0),
            "duration_fit": metrics.get("duration_fit", 0.0),
            "turn_completeness": turn_completeness,
        }
        story_weights = {
            "story_alignment": 0.36,
            "hook_strength": 0.22,
            "duration_fit": 0.2,
            "turn_completeness": 0.22,
        }
        if spoken_beat_completeness > turn_completeness + 0.01:
            story_values["spoken_beat_completeness"] = spoken_beat_completeness
            story_weights["spoken_beat_completeness"] = 0.12
            story_weights["duration_fit"] = 0.14
            story_weights["hook_strength"] = 0.18
        if question_answer_flow > 0.0:
            story_values["question_answer_flow"] = question_answer_flow
            story_weights["question_answer_flow"] = 0.06
            story_weights["story_alignment"] = 0.32
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
        story_values = {
            "story_alignment": metrics.get("story_alignment", 0.0),
            "visual_novelty": metrics.get("visual_novelty", 0.0),
            "duration_fit": metrics.get("duration_fit", 0.0),
            "motion_energy": metrics.get("motion_energy", 0.0),
        }
        story_weights = {
            "story_alignment": 0.38,
            "visual_novelty": 0.28,
            "duration_fit": 0.2,
            "motion_energy": 0.14,
        }

    clip_score = clip_score_for_segment(segment)
    if clip_score is not None:
        semantic_values["clip_score"] = clip_score
        semantic_weights["clip_score"] = 0.12 if analysis_mode == "speech" else 0.15

    return analysis_mode, {
        "technical": ScoreComponentInputs(
            values=technical_values,
            weights=technical_weights,
            blend_weight=COMPONENT_BLEND_WEIGHTS["technical"],
        ),
        "semantic": ScoreComponentInputs(
            values=semantic_values,
            weights=semantic_weights,
            blend_weight=COMPONENT_BLEND_WEIGHTS["semantic"],
        ),
        "story": ScoreComponentInputs(
            values=story_values,
            weights=story_weights,
            blend_weight=COMPONENT_BLEND_WEIGHTS["story"],
        ),
    }


def score_contributions(asset: Asset, segment: CandidateSegment) -> dict[str, float]:
    _analysis_mode, components = score_component_inputs(asset, segment)
    contributions: dict[str, float] = defaultdict(float)

    for component in components.values():
        denominator = sum(component.weights.get(key, 0.0) for key in component.values)
        if denominator == 0:
            continue
        for key, value in component.values.items():
            weight = component.weights.get(key, 0.0)
            contributions[key] += clamp(value) * (weight / denominator) * component.blend_weight

    return {key: round(value, 6) for key, value in contributions.items()}


def top_score_driver_labels(asset: Asset, segment: CandidateSegment, limit: int = 3) -> list[str]:
    contributions = score_contributions(asset, segment)
    ranked = sorted(
        contributions.items(),
        key=lambda item: (-item[1], DRIVER_LABELS.get(item[0], item[0])),
    )
    return [label_for_driver(key) for key, value in ranked if value > 0][:limit]


def limiting_factor_labels(
    asset: Asset,
    segment: CandidateSegment,
    reference_segment: CandidateSegment,
    limit: int = 2,
) -> list[str]:
    current = score_contributions(asset, segment)
    reference = score_contributions(asset, reference_segment)
    ranked = sorted(
        (
            (key, reference.get(key, 0.0) - current.get(key, 0.0))
            for key in set(reference) | set(current)
        ),
        key=lambda item: (-item[1], DRIVER_LABELS.get(item[0], item[0])),
    )
    return [label_for_driver(key) for key, delta in ranked if delta > 0][:limit]


def clip_score_for_segment(segment: CandidateSegment) -> float | None:
    if segment.prefilter is None:
        return None
    return segment.prefilter.metrics_snapshot.get("clip_score")


def label_for_driver(key: str) -> str:
    return DRIVER_LABELS.get(key, key.replace("_", " "))


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def weighted_average(
    values: dict[str, float],
    weights: dict[str, float],
    blend_weight: float | None = None,
) -> float:
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
