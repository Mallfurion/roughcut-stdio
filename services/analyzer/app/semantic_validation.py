from __future__ import annotations

from dataclasses import replace

from .ai import DeterministicVisionLanguageAnalyzer, VisionLanguageAnalyzer
from .domain import Asset, BoundaryValidationResult, CandidateSegment
from .segmentation import make_candidate_segment
from .shared.numbers import clamp
from .transcripts import TranscriptProvider, TranscriptSpan, TranscriptTurn, transcript_turns_for_range


def semantic_boundary_ambiguity_score(segment: CandidateSegment) -> float:
    prefilter = segment.prefilter
    if prefilter is None:
        return 0.0

    score = 1.0 - clamp(prefilter.boundary_confidence)
    if prefilter.boundary_strategy in {"legacy", "duration-rule", "scene-duration"}:
        score += 0.18
    if prefilter.boundary_strategy.startswith("assembly-merge:structural"):
        score += 0.16
    if prefilter.assembly_operation == "split":
        score += 0.2
    if prefilter.assembly_operation == "merge" and prefilter.assembly_rule_family == "structural-continuity":
        score += 0.12

    duration = segment.end_sec - segment.start_sec
    seed_drift_sec = boundary_seed_center_drift(segment)
    if prefilter.boundary_strategy in {"audio-snap", "scene-snap"} and seed_drift_sec >= 1.0:
        score += 0.08
    if prefilter.boundary_strategy == "transcript-snap" and seed_drift_sec >= 0.75:
        score += 0.04
    if prefilter.boundary_strategy == "turn-snap" and seed_drift_sec >= 0.5:
        score += 0.03
    if segment.analysis_mode == "speech" and prefilter.transcript_turn_alignment == "partial-turn":
        score += 0.08
    if segment.analysis_mode == "speech" and prefilter.transcript_turn_alignment == "mostly-complete":
        score += 0.03
    if segment.analysis_mode == "speech" and prefilter.assembly_rule_family == "turn-break":
        score += 0.14
    if segment.analysis_mode == "speech" and prefilter.assembly_rule_family == "turn-continuity":
        score += 0.04
    if segment.analysis_mode == "speech" and len(prefilter.transcript_turn_ids) >= 2:
        score += 0.05
    if segment.analysis_mode == "speech" and segment.quality_metrics.get("turn_completeness", 0.0) < 0.7:
        score += 0.06
    if segment.analysis_mode == "speech" and segment.quality_metrics.get("turn_completeness", 0.0) < 0.5:
        score += 0.08
    if segment.analysis_mode == "speech" and 2.0 <= duration <= 7.0:
        score += 0.08
    if segment.analysis_mode == "visual" and segment.quality_metrics.get("motion_energy", 0.0) >= 0.65:
        score += 0.06

    return round(clamp(score), 4)


def boundary_seed_center_drift(segment: CandidateSegment) -> float:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.seed_region_ranges_sec:
        return 0.0

    seed_centers = [
        (item[0] + item[1]) / 2.0
        for item in prefilter.seed_region_ranges_sec
        if len(item) == 2 and item[1] > item[0]
    ]
    if not seed_centers:
        return 0.0

    segment_center = (segment.start_sec + segment.end_sec) / 2.0
    seed_center = sum(seed_centers) / len(seed_centers)
    return abs(segment_center - seed_center)


def semantic_validation_is_available(analyzer: VisionLanguageAnalyzer) -> bool:
    return analyzer.requires_keyframes and not isinstance(analyzer, DeterministicVisionLanguageAnalyzer)


def select_semantic_boundary_validation_targets(
    *,
    segments: list[CandidateSegment],
    enabled: bool,
    analyzer_available: bool,
    ambiguity_threshold: float,
    floor_threshold: float,
    min_targets: int,
) -> tuple[dict[str, float], list[str], dict[str, str]]:
    ambiguity_by_id = {
        segment.id: semantic_boundary_ambiguity_score(segment)
        for segment in segments
    }
    target_reasons: dict[str, str] = {}
    if not enabled or not analyzer_available:
        return ambiguity_by_id, [], target_reasons

    eligible = [
        segment
        for segment in segments
        if ambiguity_by_id.get(segment.id, 0.0) >= ambiguity_threshold
    ]
    ordered = sorted(
        eligible,
        key=lambda segment: (
            ambiguity_by_id.get(segment.id, 0.0),
            segment.prefilter.score if segment.prefilter is not None else 0.0,
        ),
        reverse=True,
    )
    if not ordered and min_targets > 0:
        floor_candidates = [
            segment
            for segment in segments
            if ambiguity_by_id.get(segment.id, 0.0) >= floor_threshold
        ]
        ordered = sorted(
            floor_candidates,
            key=lambda segment: (
                ambiguity_by_id.get(segment.id, 0.0),
                segment.prefilter.score if segment.prefilter is not None else 0.0,
            ),
            reverse=True,
        )
        if ordered:
            ordered = ordered[:min_targets]
            target_reasons = {segment.id: "floor" for segment in ordered}
    else:
        target_reasons = {segment.id: "threshold" for segment in ordered}

    return ambiguity_by_id, [segment.id for segment in ordered], target_reasons


def run_scoped_semantic_validation_budget(
    *,
    target_orders: list[list[str]],
    budget_pct: int,
    max_segments: int,
) -> int:
    if max_segments <= 0 or budget_pct <= 0:
        return 0

    total_candidates = sum(len(order) for order in target_orders)
    if total_candidates <= 0:
        return 0

    pct_limit = max(1, int(total_candidates * budget_pct / 100.0))
    return min(total_candidates, max_segments, pct_limit)


def initial_boundary_validation_result(
    *,
    segment: CandidateSegment,
    enabled: bool,
    analyzer_available: bool,
    ambiguity_score: float,
    ambiguity_threshold: float,
    targeted: bool,
    target_reason: str = "",
) -> BoundaryValidationResult:
    if ambiguity_score < ambiguity_threshold and not targeted:
        return BoundaryValidationResult(
            status="not_eligible",
            decision="keep",
            reason="Deterministic boundaries were not ambiguous enough for semantic validation.",
            confidence=0.0,
            ambiguity_score=ambiguity_score,
            target_reason=target_reason,
            original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
            suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        )
    if not enabled:
        skip_reason = "disabled"
        reason = "Semantic boundary validation is disabled."
    elif not analyzer_available:
        skip_reason = "ai_unavailable"
        reason = "Semantic boundary validation is unavailable for the active analyzer."
    elif not targeted:
        skip_reason = "over_budget"
        reason = "Semantic boundary validation was skipped because the runtime budget was exhausted."
    else:
        skip_reason = ""
        if target_reason == "floor":
            reason = "Semantic boundary validation was activated by the minimum-target floor."
        else:
            reason = "Semantic boundary validation is pending."

    status = "pending" if targeted else "skipped"
    return BoundaryValidationResult(
        status=status,
        decision="keep",
        reason=reason,
        confidence=0.0,
        ambiguity_score=ambiguity_score,
        target_reason=target_reason,
        provider="deterministic" if not targeted else "",
        provider_model="fallback-v1" if not targeted else "",
        skip_reason=skip_reason,
        applied=False,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
    )


def apply_semantic_boundary_validation(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    validation_results: dict[str, BoundaryValidationResult],
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    max_adjustment_sec: float,
) -> list[CandidateSegment]:
    updated: list[CandidateSegment] = []

    for segment in segments:
        result = validation_results.get(segment.id)
        if result is None or result.status in {"not_eligible", "skipped"}:
            if result is not None:
                segment.boundary_validation = result
            updated.append(segment)
            continue

        transformed = apply_single_boundary_validation(
            asset=asset,
            segment=segment,
            result=result,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            max_adjustment_sec=max_adjustment_sec,
        )
        updated.extend(transformed)

    return [
        replace(segment, id=f"{asset.id}-segment-{index:02d}")
        for index, segment in enumerate(updated, start=1)
    ]


def semantic_split_is_supported(
    *,
    segment: CandidateSegment,
    result: BoundaryValidationResult,
    transcript_turns: list[TranscriptTurn],
) -> bool:
    if result.decision != "split":
        return True
    prefilter = segment.prefilter
    if prefilter is None:
        return False
    if prefilter.boundary_strategy.startswith("assembly-split:"):
        return True
    if prefilter.assembly_operation == "merge":
        return True
    if len(prefilter.transcript_turn_ids) >= 2:
        return True
    matched_turns = transcript_turns_for_range(transcript_turns, segment.start_sec, segment.end_sec)
    if len(matched_turns) >= 2:
        return True
    if (
        segment.analysis_mode == "speech"
        and result.confidence >= 0.85
        and (prefilter.boundary_strategy.startswith("transcript-") or prefilter.boundary_strategy == "turn-snap")
    ):
        return True
    return False


def apply_single_boundary_validation(
    *,
    asset: Asset,
    segment: CandidateSegment,
    result: BoundaryValidationResult,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    max_adjustment_sec: float,
) -> list[CandidateSegment]:
    prefilter = segment.prefilter
    if prefilter is None:
        segment.boundary_validation = result
        return [segment]

    original_start = segment.start_sec
    original_end = segment.end_sec
    bounded_start = clamp_range_value(
        value=result.suggested_range_sec[0] if result.suggested_range_sec else original_start,
        current=original_start,
        minimum=0.0,
        maximum=min(asset.duration_sec, original_end - 1.5),
        max_adjustment_sec=max_adjustment_sec,
    )
    bounded_end = clamp_range_value(
        value=result.suggested_range_sec[1] if result.suggested_range_sec else original_end,
        current=original_end,
        minimum=max(0.0, bounded_start + 1.5),
        maximum=asset.duration_sec,
        max_adjustment_sec=max_adjustment_sec,
    )
    if bounded_end - bounded_start < 1.5:
        bounded_start, bounded_end = original_start, original_end

    if result.decision == "split" and result.split_ranges_sec:
        if not semantic_split_is_supported(
            segment=segment,
            result=result,
            transcript_turns=transcript_turns,
        ):
            result.decision = "keep"
            result.applied = False
            result.suggested_range_sec = [round(original_start, 3), round(original_end, 3)]
            segment.boundary_validation = result
            return [segment]
        split_point = clamp_range_value(
            value=result.split_ranges_sec[0][1],
            current=(original_start + original_end) / 2.0,
            minimum=original_start + 1.5,
            maximum=original_end - 1.5,
            max_adjustment_sec=max_adjustment_sec,
        )
        if split_point > original_start + 1.5 and original_end - split_point > 1.5:
            children: list[CandidateSegment] = []
            for part_index, (start_sec, end_sec) in enumerate(
                ((original_start, split_point), (split_point, original_end)),
                start=1,
            ):
                child_result = BoundaryValidationResult(
                    status=result.status,
                    decision="split",
                    reason=result.reason,
                    confidence=result.confidence,
                    ambiguity_score=result.ambiguity_score,
                    target_reason=result.target_reason,
                    provider=result.provider,
                    provider_model=result.provider_model,
                    skip_reason=result.skip_reason,
                    applied=True,
                    original_range_sec=list(result.original_range_sec),
                    suggested_range_sec=[round(start_sec, 3), round(end_sec, 3)],
                    split_ranges_sec=[list(item) for item in result.split_ranges_sec],
                )
                children.append(
                    rebuild_segment_with_validation(
                        asset=asset,
                        segment=segment,
                        new_id=f"{segment.id}-semantic-{part_index}",
                        start_sec=start_sec,
                        end_sec=end_sec,
                        transcriber=transcriber,
                        transcript_spans=transcript_spans,
                        transcript_turns=transcript_turns,
                        prefilter_signals=prefilter_signals,
                        audio_signals=audio_signals,
                        boundary_validation=child_result,
                    )
                )
            return children

    applied = result.decision in {"extend", "trim"} and (
        abs(bounded_start - original_start) > 0.01 or abs(bounded_end - original_end) > 0.01
    )
    result.applied = applied
    result.suggested_range_sec = [round(bounded_start, 3), round(bounded_end, 3)]
    if not applied:
        segment.boundary_validation = result
        return [segment]

    return [
        rebuild_segment_with_validation(
            asset=asset,
            segment=segment,
            new_id=segment.id,
            start_sec=bounded_start,
            end_sec=bounded_end,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            boundary_validation=result,
        )
    ]


def rebuild_segment_with_validation(
    *,
    asset: Asset,
    segment: CandidateSegment,
    new_id: str,
    start_sec: float,
    end_sec: float,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    boundary_validation: BoundaryValidationResult,
) -> CandidateSegment:
    prefilter = segment.prefilter
    if prefilter is None:
        segment.boundary_validation = boundary_validation
        return segment

    rebuilt = make_candidate_segment(
        asset=asset,
        segment_id=new_id,
        start_sec=start_sec,
        end_sec=end_sec,
        transcriber=transcriber,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
        boundary_strategy=prefilter.boundary_strategy,
        boundary_confidence=max(prefilter.boundary_confidence, boundary_validation.confidence),
        seed_region_ids=prefilter.seed_region_ids,
        seed_region_sources=prefilter.seed_region_sources,
        seed_region_ranges_sec=prefilter.seed_region_ranges_sec,
        assembly_operation=prefilter.assembly_operation,
        assembly_rule_family=prefilter.assembly_rule_family,
        assembly_source_segment_ids=prefilter.assembly_source_segment_ids,
        assembly_source_ranges_sec=prefilter.assembly_source_ranges_sec,
        transcript_lookup_enabled=bool(transcript_spans),
    )
    rebuilt.boundary_validation = boundary_validation
    return rebuilt


def clamp_range_value(
    *,
    value: float,
    current: float,
    minimum: float,
    maximum: float,
    max_adjustment_sec: float,
) -> float:
    bounded = max(minimum, min(maximum, value))
    delta_bounded = max(current - max_adjustment_sec, min(current + max_adjustment_sec, bounded))
    return round(max(minimum, min(maximum, delta_bounded)), 3)
