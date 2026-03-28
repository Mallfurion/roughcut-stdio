from __future__ import annotations

from dataclasses import dataclass
import re

from ..domain import Asset, CandidateSegment, TakeRecommendation, Timeline, TimelineItem
from ..shared.strings import dedupe_labels

TIMELINE_VISUAL_BASE_MAX_DURATION_SEC = 5.0
TIMELINE_VISUAL_REFINED_MAX_DURATION_SEC = 6.5
TIMELINE_VISUAL_MERGED_MAX_DURATION_SEC = 7.0


@dataclass(slots=True)
class StoryAssemblyChoice:
    take: TakeRecommendation
    sequence_score: float
    sequence_group: str
    sequence_role: str
    sequence_rationale: list[str]
    sequence_driver_labels: list[str]
    sequence_tradeoff_labels: list[str]


@dataclass(slots=True)
class StoryAssemblyEvaluation:
    score: float
    driver_labels: list[str]
    tradeoff_labels: list[str]
    matched_prompt_terms: list[str]


def build_timeline(
    take_recommendations: list[TakeRecommendation],
    candidate_segments: list[CandidateSegment],
    assets: list[Asset],
    story_prompt: str = "",
) -> Timeline:
    best_takes = [take for take in take_recommendations if take.is_best_take]
    segment_by_id = {segment.id: segment for segment in candidate_segments}
    asset_by_id = {asset.id: asset for asset in assets}
    assembled_choices = assemble_story_sequence(best_takes, segment_by_id, asset_by_id, story_prompt=story_prompt)

    items: list[TimelineItem] = []
    for index, choice in enumerate(assembled_choices):
        take = choice.take
        segment = segment_by_id[take.candidate_segment_id]
        asset = asset_by_id[segment.asset_id]
        duration = segment.end_sec - segment.start_sec
        trimmed_duration = min(duration, suggested_timeline_duration(segment))
        items.append(
            TimelineItem(
                id=f"timeline-item-{index + 1:02d}",
                take_recommendation_id=take.id,
                order_index=index,
                trim_in_sec=0.0,
                trim_out_sec=round(trimmed_duration, 3),
                label=timeline_label(index, len(best_takes), segment.analysis_mode),
                notes=timeline_note(segment),
                source_asset_path=asset.source_path,
                source_reel=asset.interchange_reel_name,
                sequence_group=choice.sequence_group,
                sequence_role=choice.sequence_role,
                sequence_score=round(choice.sequence_score, 4),
                sequence_rationale=list(choice.sequence_rationale),
                sequence_driver_labels=list(choice.sequence_driver_labels),
                sequence_tradeoff_labels=list(choice.sequence_tradeoff_labels),
            )
        )

    ordered_takes = [choice.take for choice in assembled_choices]
    summary = summarize_story(ordered_takes, segment_by_id)
    return Timeline(
        id="timeline-main",
        version=1,
        story_summary=summary,
        items=items,
    )


def assemble_story_sequence(
    best_takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
    asset_by_id: dict[str, Asset],
    *,
    story_prompt: str = "",
) -> list[StoryAssemblyChoice]:
    if not best_takes:
        return []
    prompt_keywords = extract_story_prompt_keywords(story_prompt)

    if len(best_takes) == 1:
        take = best_takes[0]
        segment = segment_by_id[take.candidate_segment_id]
        return [
            StoryAssemblyChoice(
                take=take,
                sequence_score=round(take.score_total, 4),
                sequence_group="setup",
                sequence_role=sequence_role_for_item(0, 1, segment),
                sequence_rationale=["Only selected beat in the current rough timeline."],
                sequence_driver_labels=["local_strength"],
                sequence_tradeoff_labels=[],
            )
        ]

    remaining = list(best_takes)
    opener_evaluations = {
        take.id: evaluate_opener_candidate(
            take,
            segment_by_id[take.candidate_segment_id],
            prompt_keywords=prompt_keywords,
        )
        for take in remaining
    }
    opener = max(remaining, key=lambda take: opener_evaluations[take.id].score)
    remaining.remove(opener)

    release_take: TakeRecommendation | None = None
    release_evaluations: dict[str, StoryAssemblyEvaluation] = {}
    if len(best_takes) >= 3 and remaining:
        release_evaluations = {
            take.id: evaluate_release_candidate(
                take,
                segment_by_id[take.candidate_segment_id],
                prompt_keywords=prompt_keywords,
            )
            for take in remaining
        }
        release_candidates = [
            take for take in remaining if segment_by_id[take.candidate_segment_id].analysis_mode == "visual"
        ]
        if not release_candidates:
            release_candidates = list(remaining)
        release_take = max(release_candidates, key=lambda take: release_evaluations[take.id].score)
        remaining.remove(release_take)

    ordered_takes = [opener]
    while remaining:
        previous = ordered_takes[-1]
        seen_segments = [segment_by_id[take.candidate_segment_id] for take in ordered_takes]
        transition_evaluations = {
            take.id: evaluate_transition_candidate(
                previous,
                take,
                segment_by_id[previous.candidate_segment_id],
                segment_by_id[take.candidate_segment_id],
                seen_segments=seen_segments,
                prompt_keywords=prompt_keywords,
            )
            for take in remaining
        }
        next_take = max(remaining, key=lambda take: transition_evaluations[take.id].score)
        ordered_takes.append(next_take)
        remaining.remove(next_take)

    if release_take is not None:
        ordered_takes.append(release_take)

    choices: list[StoryAssemblyChoice] = []
    total = len(ordered_takes)
    for index, take in enumerate(ordered_takes):
        segment = segment_by_id[take.candidate_segment_id]
        previous_segment = (
            segment_by_id[ordered_takes[index - 1].candidate_segment_id]
            if index > 0
            else None
        )
        if index == 0:
            evaluation = opener_evaluations.get(
                take.id,
                StoryAssemblyEvaluation(
                    score=take.score_total,
                    driver_labels=["local_strength"],
                    tradeoff_labels=[],
                    matched_prompt_terms=[],
                ),
            )
        elif release_take is not None and take.id == release_take.id:
            evaluation = release_evaluations.get(
                take.id,
                StoryAssemblyEvaluation(
                    score=take.score_total,
                    driver_labels=["local_strength"],
                    tradeoff_labels=[],
                    matched_prompt_terms=[],
                ),
            )
        else:
            evaluation = evaluate_transition_candidate(
                ordered_takes[index - 1],
                take,
                previous_segment if previous_segment is not None else segment,
                segment,
                seen_segments=[segment_by_id[item.candidate_segment_id] for item in ordered_takes[:index]],
                prompt_keywords=prompt_keywords,
            )
        choices.append(
            StoryAssemblyChoice(
                take=take,
                sequence_score=round(evaluation.score, 4),
                sequence_group=sequence_group_for_item(index, total),
                sequence_role=sequence_role_for_item(index, total, segment),
                sequence_rationale=sequence_rationale_for_item(
                    index=index,
                    total=total,
                    current_take=take,
                    current_segment=segment,
                    previous_segment=previous_segment,
                    release_reserved=release_take is not None and take.id == release_take.id,
                    asset_by_id=asset_by_id,
                    driver_labels=evaluation.driver_labels,
                    tradeoff_labels=evaluation.tradeoff_labels,
                    prompt_terms=evaluation.matched_prompt_terms,
                ),
                sequence_driver_labels=list(evaluation.driver_labels),
                sequence_tradeoff_labels=list(evaluation.tradeoff_labels),
            )
        )
    return choices


def has_mixed_sequence_modes(
    takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
) -> bool:
    modes = {segment_by_id[take.candidate_segment_id].analysis_mode for take in takes}
    return len(modes) > 1


def evaluate_opener_candidate(
    take: TakeRecommendation,
    segment: CandidateSegment,
    *,
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = take.score_total
    driver_labels = ["local_strength"]
    tradeoff_labels: list[str] = []
    if segment.analysis_mode == "visual":
        score += 0.09
        driver_labels.append("opener_fit")
        if segment.quality_metrics.get("visual_novelty", 0.0) >= 0.7:
            score += 0.04
            driver_labels.append("visual_novelty")
    else:
        score += 0.03
        if not segment.transcript_excerpt.strip():
            score -= 0.03
    if segment.quality_metrics.get("hook_strength", 0.0) >= 0.7:
        score += 0.03
        driver_labels.append("hook_strength")
    prompt_fit, matched_terms = segment_prompt_fit(segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += prompt_fit
        driver_labels.append("prompt_fit")
        if segment.analysis_mode == "visual":
            score += 0.02
            driver_labels.append("prompt_led_opener")
        if take.score_total < 0.78:
            tradeoff_labels.append("preferred_for_prompt_fit")
    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def evaluate_release_candidate(
    take: TakeRecommendation,
    segment: CandidateSegment,
    *,
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = take.score_total
    driver_labels = ["local_strength", "release_fit"]
    tradeoff_labels: list[str] = []
    if segment.analysis_mode == "visual":
        score += 0.08
        if segment.quality_metrics.get("motion_energy", 0.0) <= 0.55:
            score += 0.04
            driver_labels.append("calm_release")
    elif segment.quality_metrics.get("turn_completeness", 0.0) >= 0.85:
        score += 0.03
        driver_labels.append("complete_turn")
    if segment.quality_metrics.get("story_alignment", 0.0) >= 0.7:
        score += 0.03
        driver_labels.append("story_alignment")
    prompt_fit, matched_terms = segment_prompt_fit(segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += min(0.05, prompt_fit)
        driver_labels.append("prompt_fit")
    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def evaluate_transition_candidate(
    previous_take: TakeRecommendation,
    current_take: TakeRecommendation,
    previous_segment: CandidateSegment,
    current_segment: CandidateSegment,
    *,
    seen_segments: list[CandidateSegment],
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = current_take.score_total
    driver_labels = ["local_strength"]
    tradeoff_labels: list[str] = []
    if current_segment.analysis_mode != previous_segment.analysis_mode:
        score += 0.08
        driver_labels.extend(["mode_variety", "repetition_control"])
        if previous_segment.analysis_mode == "visual" and current_segment.analysis_mode == "speech":
            score += 0.04
            driver_labels.append("spoken_progression")
        if previous_segment.analysis_mode == "speech" and current_segment.analysis_mode == "visual":
            score += 0.05
            driver_labels.append("release_transition")
    else:
        score -= 0.04
        tradeoff_labels.append("same_mode_repeat")

    if segment_story_role(previous_segment) != segment_story_role(current_segment):
        score += 0.04
        driver_labels.extend(["role_variety", "repetition_control"])
    else:
        score -= 0.03
        tradeoff_labels.append("same_role_repeat")

    if (
        current_segment.analysis_mode == "speech"
        and current_segment.quality_metrics.get("turn_completeness", 0.0) >= 0.85
    ):
        score += 0.02
        driver_labels.append("complete_turn")

    if previous_take.score_total >= 0.75 and current_take.score_total >= 0.75:
        score += 0.01
        driver_labels.append("paired_strength")

    prompt_fit, matched_terms = segment_prompt_fit(current_segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += min(0.06, prompt_fit)
        driver_labels.append("prompt_fit")

    if seen_segments:
        recent_modes = [segment.analysis_mode for segment in seen_segments[-2:]]
        if recent_modes and all(mode == current_segment.analysis_mode for mode in recent_modes):
            score -= 0.05
            tradeoff_labels.append("third_same_mode_avoided")
        recent_roles = [segment_story_role(segment) for segment in seen_segments[-2:]]
        current_role = segment_story_role(current_segment)
        if recent_roles and all(role == current_role for role in recent_roles):
            score -= 0.04
            tradeoff_labels.append("third_same_role_avoided")

    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def segment_story_role(segment: CandidateSegment) -> str:
    if segment.ai_understanding and segment.ai_understanding.story_roles:
        return segment.ai_understanding.story_roles[0]
    if segment.analysis_mode == "speech":
        return "spoken beat"
    metrics = segment.quality_metrics
    if metrics.get("visual_novelty", 0.0) >= 0.8 and metrics.get("motion_energy", 0.0) >= 0.7:
        return "dynamic establishing"
    if metrics.get("motion_energy", 0.0) < 0.45:
        return "calm texture"
    if metrics.get("subject_clarity", 0.0) >= 0.8:
        return "clear detail"
    return "transition-ready"


def sequence_group_for_item(index: int, count: int) -> str:
    if count <= 1 or index == 0:
        return "setup"
    if index == count - 1:
        return "release"
    return "development"


def sequence_role_for_item(index: int, count: int, segment: CandidateSegment) -> str:
    if index == 0:
        return "opener"
    if index == count - 1:
        return "release"
    if segment.analysis_mode == "speech":
        return "spoken beat"
    return "visual bridge"


def sequence_rationale_for_item(
    *,
    index: int,
    total: int,
    current_take: TakeRecommendation,
    current_segment: CandidateSegment,
    previous_segment: CandidateSegment | None,
    release_reserved: bool,
    asset_by_id: dict[str, Asset],
    driver_labels: list[str],
    tradeoff_labels: list[str],
    prompt_terms: list[str],
) -> list[str]:
    asset = asset_by_id[current_segment.asset_id]
    reasons: list[str] = []
    if index == 0:
        if current_segment.analysis_mode == "visual":
            reasons.append("Starts on a visual anchor to establish the cut cleanly.")
        else:
            reasons.append("Starts on the strongest spoken beat available.")
        if current_segment.quality_metrics.get("hook_strength", 0.0) >= 0.7:
            reasons.append("Its hook strength makes it a stable opener.")
    else:
        if previous_segment is not None and previous_segment.analysis_mode != current_segment.analysis_mode:
            reasons.append(
                f"Alternates from {previous_segment.analysis_mode} to {current_segment.analysis_mode} to keep sequence contrast."
            )
        if previous_segment is not None and segment_story_role(previous_segment) != segment_story_role(current_segment):
            reasons.append("Adds role variety instead of repeating the same beat type.")
        if current_segment.analysis_mode == "speech" and current_segment.transcript_excerpt.strip():
            reasons.append("Moves the sequence forward with readable spoken information.")
        elif current_segment.analysis_mode == "visual":
            reasons.append("Provides visual pacing between stronger information beats.")

    if release_reserved:
        reasons.append("Held for the end because it reads as a cleaner release beat.")
    if index == total - 1 and not release_reserved:
        reasons.append("Closes the current rough cut without needing another transition.")
    if "prompt_fit" in driver_labels and prompt_terms:
        reasons.append(f"Matches story prompt cues: {', '.join(prompt_terms[:2])}.")
    if "repetition_control" in driver_labels:
        reasons.append("Avoids repeating the same beat pattern too closely.")
    if tradeoff_labels and current_take.score_total < 0.8:
        reasons.append("Accepts a bounded local-score tradeoff for stronger sequence fit.")
    if current_take.score_total >= 0.78:
        reasons.append(f"Carries strong local quality at {round(current_take.score_total * 100):d}/100.")
    reasons.append(f"Source {asset.interchange_reel_name}.")
    return reasons[:4]


def extract_story_prompt_keywords(story_prompt: str) -> set[str]:
    if not story_prompt.strip():
        return set()
    stopwords = {
        "about",
        "after",
        "before",
        "build",
        "from",
        "into",
        "make",
        "moment",
        "move",
        "rough",
        "short",
        "story",
        "that",
        "then",
        "this",
        "through",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", story_prompt.lower())
        if len(token) >= 4 and token not in stopwords
    }


def segment_prompt_fit(segment: CandidateSegment, prompt_keywords: set[str]) -> tuple[float, list[str]]:
    if not prompt_keywords:
        return 0.0, []
    searchable_parts = [
        segment.transcript_excerpt,
        segment.description,
        " ".join(segment.ai_understanding.story_roles) if segment.ai_understanding else "",
        " ".join(segment.ai_understanding.subjects) if segment.ai_understanding else "",
        " ".join(segment.ai_understanding.actions) if segment.ai_understanding else "",
        segment.ai_understanding.summary if segment.ai_understanding else "",
    ]
    searchable = " ".join(part for part in searchable_parts if part).lower()
    matched_terms = sorted(term for term in prompt_keywords if term in searchable)
    if not matched_terms:
        return 0.0, []
    return min(0.08, 0.02 * len(matched_terms)), matched_terms[:3]


def suggested_timeline_duration(segment: CandidateSegment) -> float:
    duration = max(0.0, segment.end_sec - segment.start_sec)
    if segment.analysis_mode == "speech":
        return min(duration, 7.5)
    prefilter = segment.prefilter
    if prefilter is None:
        return min(duration, TIMELINE_VISUAL_BASE_MAX_DURATION_SEC)
    if prefilter.assembly_operation == "merge" or prefilter.boundary_strategy.startswith("assembly-merge:"):
        return min(duration, TIMELINE_VISUAL_MERGED_MAX_DURATION_SEC)
    if (
        prefilter.boundary_strategy in {"scene-snap", "audio-snap", "transcript-snap"}
        or prefilter.boundary_confidence >= 0.6
    ):
        return min(duration, TIMELINE_VISUAL_REFINED_MAX_DURATION_SEC)
    return min(duration, TIMELINE_VISUAL_BASE_MAX_DURATION_SEC)


def timeline_label(index: int, count: int, analysis_mode: str) -> str:
    if index == 0:
        return "Opener"
    if index == count - 1:
        return "Outro"
    return "Narrative beat" if analysis_mode == "speech" else "Visual bridge"


def timeline_note(segment: CandidateSegment) -> str:
    if segment.analysis_mode == "speech":
        return "Protect the spoken beat and keep the line readable."
    return "Use this as visual pacing or atmospheric coverage."


def summarize_story(
    best_takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
) -> str:
    if not best_takes:
        return "No best takes have been selected yet."

    modes = [segment_by_id[take.candidate_segment_id].analysis_mode for take in best_takes]
    if all(mode == "visual" for mode in modes):
        return "The cut leans on visual progression, using silent coverage to move from setup to payoff."
    if all(mode == "speech" for mode in modes):
        return "The cut is dialogue-led and organized around spoken beats."
    return "The cut opens visually, turns on spoken information where available, and returns to visual release."
