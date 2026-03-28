from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import md5

from .domain import Asset, CandidateSegment, PrefilterDecision
from .prefilter import SeedRegion, aggregate_segment_prefilter
from .scoring import infer_analysis_mode
from .shared.numbers import clamp
from .transcripts import (
    ASSEMBLY_TRANSCRIPT_CONTINUITY_GAP_SEC,
    SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC,
    SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC,
    TRANSCRIPT_TURN_BREAK_GAP_SEC,
    TRANSCRIPT_TURN_CONTINUITY_GAP_SEC,
    TRANSCRIPT_TURN_REFINE_MARGIN_SEC,
    TranscriptProvider,
    TranscriptSpan,
    TranscriptTurn,
    derive_spoken_structure,
    is_question_like_text,
    transcript_turn_alignment,
    transcript_turns_for_range,
)

AUDIO_SNAP_MAX_CENTER_DRIFT_SEC = 2.0
ASSEMBLY_MERGE_MAX_GAP_SEC = 1.25
ASSEMBLY_MERGE_STRUCTURAL_GAP_SEC = 0.4
ASSEMBLY_MERGE_STRUCTURAL_MAX_DURATION_SEC = 7.5
ASSEMBLY_SPLIT_MIN_DURATION_SEC = 6.5
ASSEMBLY_SPLIT_MIN_PART_SEC = 2.0
ASSEMBLY_SPLIT_TRANSCRIPT_GAP_SEC = 1.25
ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC = 1.5


@dataclass(slots=True)
class RefinedSegmentCandidate:
    start_sec: float
    end_sec: float
    boundary_strategy: str
    boundary_confidence: float
    seed_region_ids: list[str]
    seed_region_sources: list[str]
    seed_region_ranges_sec: list[list[float]]
    transcript_turn_ids: list[str] | None = None
    transcript_turn_ranges_sec: list[list[float]] | None = None
    transcript_turn_alignment: str = ""


@dataclass(slots=True)
class AssemblyContinuitySignals:
    gap_sec: float
    transcript_span_count: int
    transcript_internal_gap_sec: float
    transcript_turn_count: int
    transcript_turn_gap_sec: float
    same_analysis_mode: bool
    shared_seed_source: bool
    scene_divider_between: bool
    shared_turn: bool
    consecutive_turns: bool
    strong_turn_break_between: bool
    question_answer_flow: bool
    monologue_continuity: bool


def transcript_excerpt_for_range(
    transcriber: TranscriptProvider,
    asset: Asset,
    transcript_spans: list[TranscriptSpan],
    start_sec: float,
    end_sec: float,
    *,
    allow_provider_lookup: bool = True,
) -> str:
    matching = [
        span.text.strip()
        for span in transcript_spans
        if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text.strip()
    ]
    if matching:
        return " ".join(matching).strip()
    if not allow_provider_lookup:
        return ""
    return transcriber.excerpt(asset, start_sec, end_sec).strip()


def make_candidate_segment(
    *,
    asset: Asset,
    segment_id: str,
    start_sec: float,
    end_sec: float,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    boundary_strategy: str,
    boundary_confidence: float,
    seed_region_ids: list[str],
    seed_region_sources: list[str],
    seed_region_ranges_sec: list[list[float]],
    transcript_lookup_enabled: bool = True,
    assembly_operation: str = "none",
    assembly_rule_family: str = "",
    assembly_source_segment_ids: list[str] | None = None,
    assembly_source_ranges_sec: list[list[float]] | None = None,
) -> CandidateSegment:
    matching_spans = (
        [
            span
            for span in transcript_spans
            if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text.strip()
        ]
        if asset.has_speech
        else []
    )
    excerpt = (
        transcript_excerpt_for_range(
            transcriber,
            asset,
            matching_spans,
            start_sec,
            end_sec,
            allow_provider_lookup=transcript_lookup_enabled,
        )
        if asset.has_speech
        else ""
    )
    matched_turns, turn_alignment, turn_completeness = transcript_turn_alignment(
        transcript_turns,
        start_sec,
        end_sec,
    )
    spoken_structure = derive_spoken_structure(
        matching_spans,
        start_sec=start_sec,
        end_sec=end_sec,
        turn_completeness=turn_completeness,
    )
    prefilter_snapshot = aggregate_segment_prefilter(
        signals=prefilter_signals,
        start_sec=start_sec,
        end_sec=end_sec,
        audio_signals=audio_signals,
    )
    metrics = synthesize_quality_metrics(
        asset,
        start_sec,
        end_sec,
        "visual",
        prefilter_snapshot=prefilter_snapshot["metrics_snapshot"],
    )
    metrics["turn_completeness"] = turn_completeness
    metrics["transcript_turn_count"] = float(len(matched_turns))
    metrics["question_answer_flow"] = spoken_structure.question_answer_flow
    metrics["monologue_continuity"] = spoken_structure.monologue_continuity
    metrics["spoken_beat_completeness"] = spoken_structure.spoken_beat_completeness
    analysis_mode, _analysis_mode_source = infer_analysis_mode(asset, excerpt, metrics)
    return CandidateSegment(
        id=segment_id,
        asset_id=asset.id,
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        analysis_mode=analysis_mode,
        transcript_excerpt=excerpt,
        description=describe_segment(asset, start_sec, end_sec, excerpt, metrics, analysis_mode=analysis_mode),
        quality_metrics=metrics,
        prefilter=PrefilterDecision(
            score=float(prefilter_snapshot["score"]),
            shortlisted=False,
            filtered_before_vlm=False,
            selection_reason="Segment has not been evaluated for VLM shortlist yet.",
            sampled_frame_count=int(prefilter_snapshot["sampled_frame_count"]),
            sampled_frame_timestamps_sec=list(prefilter_snapshot["sampled_frame_timestamps_sec"]),
            top_frame_timestamps_sec=list(prefilter_snapshot["top_frame_timestamps_sec"]),
            metrics_snapshot=dict(prefilter_snapshot["metrics_snapshot"]),
            boundary_strategy=boundary_strategy,
            boundary_confidence=boundary_confidence,
            seed_region_ids=list(seed_region_ids),
            seed_region_sources=list(seed_region_sources),
            seed_region_ranges_sec=[list(item) for item in seed_region_ranges_sec],
            assembly_operation=assembly_operation,
            assembly_rule_family=assembly_rule_family,
            assembly_source_segment_ids=list(assembly_source_segment_ids or []),
            assembly_source_ranges_sec=[list(item) for item in (assembly_source_ranges_sec or [])],
            transcript_turn_ids=[turn.id for turn in matched_turns],
            transcript_turn_ranges_sec=[[turn.start_sec, turn.end_sec] for turn in matched_turns],
            transcript_turn_alignment=turn_alignment,
            speech_structure_label=spoken_structure.label,
            speech_structure_cues=list(spoken_structure.cues),
            speech_structure_confidence=spoken_structure.confidence,
        ),
    )


def refine_seed_regions(
    *,
    asset: Asset,
    seed_regions: list[SeedRegion],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    audio_signals,
) -> list[RefinedSegmentCandidate]:
    if not seed_regions:
        return []

    refined: list[RefinedSegmentCandidate] = []
    for seed in seed_regions:
        candidate = (
            _refine_seed_with_transcript(asset, seed, transcript_spans, transcript_turns)
            or _refine_seed_with_audio(asset, seed, audio_signals)
            or _refine_seed_with_scene(asset, seed, base_ranges)
            or _refine_seed_with_duration(asset, seed)
        )
        refined.append(candidate)
    return _dedupe_refined_candidates(refined)


def _refine_seed_with_transcript(
    asset: Asset,
    seed: SeedRegion,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
) -> RefinedSegmentCandidate | None:
    expanded_start = max(0.0, seed.start_sec - TRANSCRIPT_TURN_REFINE_MARGIN_SEC)
    expanded_end = min(asset.duration_sec, seed.end_sec + TRANSCRIPT_TURN_REFINE_MARGIN_SEC)
    if transcript_turns:
        matching_turns = transcript_turns_for_range(transcript_turns, expanded_start, expanded_end)
        if matching_turns:
            matching_turns = extend_transcript_turn_window(matching_turns, transcript_turns)
            start_sec = max(0.0, min(turn.start_sec for turn in matching_turns))
            end_sec = min(asset.duration_sec, max(turn.end_sec for turn in matching_turns))
            if end_sec - start_sec >= 1.0:
                return RefinedSegmentCandidate(
                    start_sec=round(start_sec, 3),
                    end_sec=round(end_sec, 3),
                    boundary_strategy="turn-snap",
                    boundary_confidence=0.93,
                    seed_region_ids=[seed.id],
                    seed_region_sources=[seed.source],
                    seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
                    transcript_turn_ids=[turn.id for turn in matching_turns],
                    transcript_turn_ranges_sec=[[turn.start_sec, turn.end_sec] for turn in matching_turns],
                    transcript_turn_alignment="turn-aligned",
                )
    if not transcript_spans:
        return None
    matching = [
        span
        for span in transcript_spans
        if span.end_sec >= expanded_start and span.start_sec <= expanded_end
    ]
    if not matching:
        return None
    start_sec = max(0.0, min(span.start_sec for span in matching))
    end_sec = min(asset.duration_sec, max(span.end_sec for span in matching))
    if end_sec - start_sec < 1.0:
        return None
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy="transcript-snap",
        boundary_confidence=0.9,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
        transcript_turn_ids=[],
        transcript_turn_ranges_sec=[],
        transcript_turn_alignment="span-aligned",
    )


def extend_transcript_turn_window(
    matching_turns: list[TranscriptTurn],
    transcript_turns: list[TranscriptTurn],
) -> list[TranscriptTurn]:
    if not matching_turns or not transcript_turns:
        return matching_turns
    ordered_all = {turn.id: index for index, turn in enumerate(transcript_turns)}
    extended = list(matching_turns)
    last_turn = extended[-1]
    last_index = ordered_all.get(last_turn.id, -1)
    if last_index < 0 or last_index >= len(transcript_turns) - 1:
        return extended
    next_turn = transcript_turns[last_index + 1]
    gap_sec = max(0.0, next_turn.start_sec - last_turn.end_sec)
    if is_question_like_text(last_turn.text) and gap_sec <= SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC:
        extended.append(next_turn)
        return extended
    if (
        not is_question_like_text(last_turn.text)
        and not is_question_like_text(next_turn.text)
        and gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
        and len(extended) == 1
    ):
        extended.append(next_turn)
    return extended


def _refine_seed_with_audio(
    asset: Asset,
    seed: SeedRegion,
    audio_signals,
) -> RefinedSegmentCandidate | None:
    if not audio_signals:
        return None
    energetic = [sig for sig in audio_signals if not sig.is_silent and sig.rms_energy >= 0.05]
    if not energetic:
        return None
    center = (seed.start_sec + seed.end_sec) / 2.0
    nearest_idx = min(range(len(audio_signals)), key=lambda idx: abs(audio_signals[idx].timestamp_sec - center))
    if audio_signals[nearest_idx].is_silent or audio_signals[nearest_idx].rms_energy < 0.05:
        nearest_idx = min(range(len(energetic)), key=lambda idx: abs(energetic[idx].timestamp_sec - center))
        center_signal = energetic[nearest_idx]
        nearest_idx = next(
            idx for idx, signal in enumerate(audio_signals)
            if signal.timestamp_sec == center_signal.timestamp_sec and signal.rms_energy == center_signal.rms_energy
        )

    left_idx = nearest_idx
    while left_idx > 0 and not audio_signals[left_idx - 1].is_silent and audio_signals[left_idx - 1].rms_energy >= 0.05:
        left_idx -= 1
    right_idx = nearest_idx
    while right_idx < len(audio_signals) - 1 and not audio_signals[right_idx + 1].is_silent and audio_signals[right_idx + 1].rms_energy >= 0.05:
        right_idx += 1

    step = _average_signal_step(audio_signals)
    start_sec = max(0.0, audio_signals[left_idx].timestamp_sec - step / 2.0)
    end_sec = min(asset.duration_sec, audio_signals[right_idx].timestamp_sec + step / 2.0)
    snapped_center = (start_sec + end_sec) / 2.0
    if abs(snapped_center - center) > AUDIO_SNAP_MAX_CENTER_DRIFT_SEC:
        return None
    if end_sec - start_sec < 1.0:
        return None
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy="audio-snap",
        boundary_confidence=0.74,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _refine_seed_with_scene(
    asset: Asset,
    seed: SeedRegion,
    base_ranges: list[tuple[float, float]],
) -> RefinedSegmentCandidate | None:
    if not base_ranges:
        return None
    center = (seed.start_sec + seed.end_sec) / 2.0
    containing = [item for item in base_ranges if item[0] <= center <= item[1]]
    if containing:
        scene_start, scene_end = containing[0]
    else:
        scene_start, scene_end = max(
            base_ranges,
            key=lambda item: min(item[1], seed.end_sec) - max(item[0], seed.start_sec),
        )
    if scene_end - scene_start > 8.0:
        return _refine_seed_with_duration(asset, seed, strategy="scene-duration")
    return RefinedSegmentCandidate(
        start_sec=round(max(0.0, scene_start), 3),
        end_sec=round(min(asset.duration_sec, scene_end), 3),
        boundary_strategy="scene-snap",
        boundary_confidence=0.62,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _refine_seed_with_duration(
    asset: Asset,
    seed: SeedRegion,
    *,
    strategy: str = "duration-rule",
) -> RefinedSegmentCandidate:
    center = (seed.start_sec + seed.end_sec) / 2.0
    duration = max(1.5, min(6.0, seed.end_sec - seed.start_sec))
    half = duration / 2.0
    start_sec = max(0.0, center - half)
    end_sec = min(asset.duration_sec, center + half)
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy=strategy,
        boundary_confidence=0.48,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _average_signal_step(signals) -> float:
    if len(signals) < 2:
        return 1.0
    deltas = [
        later.timestamp_sec - earlier.timestamp_sec
        for earlier, later in zip(signals, signals[1:])
        if later.timestamp_sec > earlier.timestamp_sec
    ]
    if not deltas:
        return 1.0
    return sum(deltas) / len(deltas)


def _dedupe_refined_candidates(candidates: list[RefinedSegmentCandidate]) -> list[RefinedSegmentCandidate]:
    if not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda item: (item.boundary_confidence, -(item.end_sec - item.start_sec)),
        reverse=True,
    )
    kept: list[RefinedSegmentCandidate] = []
    for candidate in ordered:
        if any(
            _range_overlap_ratio((candidate.start_sec, candidate.end_sec), (existing.start_sec, existing.end_sec)) >= 0.9
            for existing in kept
        ):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda item: item.start_sec)


def _range_overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end <= start:
        return 0.0
    overlap = end - start
    shorter = min(a[1] - a[0], b[1] - b[0])
    return overlap / shorter if shorter > 0 else 0.0


def assemble_narrative_units(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    if not segments:
        return []

    split_segments: list[CandidateSegment] = []
    for segment in sorted(segments, key=lambda item: item.start_sec):
        split_segments.extend(
            split_candidate_segment(
                asset=asset,
                segment=segment,
                base_ranges=base_ranges,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                transcriber=transcriber,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
            )
        )

    merged_segments = merge_adjacent_segments(
        asset=asset,
        segments=split_segments,
        base_ranges=base_ranges,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        transcriber=transcriber,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
    )

    return [
        replace(segment, id=f"{asset.id}-segment-{index:02d}")
        for index, segment in enumerate(merged_segments, start=1)
    ]


def split_candidate_segment(
    *,
    asset: Asset,
    segment: CandidateSegment,
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    divider, rule_family = _find_segment_split_divider(segment, base_ranges, transcript_spans, transcript_turns)
    if divider is None or not rule_family:
        return [segment]

    prefilter = segment.prefilter
    if prefilter is None:
        return [segment]

    boundary_confidence = round(clamp(max(prefilter.boundary_confidence, 0.45) * 0.92), 4)
    source_segment_ids = assembly_source_segment_ids(segment)
    source_ranges = assembly_source_ranges_sec(segment)
    split_ranges = [(segment.start_sec, divider), (divider, segment.end_sec)]
    parts: list[CandidateSegment] = []
    for part_index, (start_sec, end_sec) in enumerate(split_ranges, start=1):
        if end_sec - start_sec < ASSEMBLY_SPLIT_MIN_PART_SEC:
            return [segment]
        parts.append(
            make_candidate_segment(
                asset=asset,
                segment_id=f"{segment.id}-split-{part_index}",
                start_sec=start_sec,
                end_sec=end_sec,
                transcriber=transcriber,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
                boundary_strategy=f"assembly-split:{rule_family}",
                boundary_confidence=boundary_confidence,
                seed_region_ids=prefilter.seed_region_ids,
                seed_region_sources=prefilter.seed_region_sources,
                seed_region_ranges_sec=prefilter.seed_region_ranges_sec,
                transcript_lookup_enabled=bool(transcript_spans),
                assembly_operation="split",
                assembly_rule_family=rule_family,
                assembly_source_segment_ids=source_segment_ids,
                assembly_source_ranges_sec=source_ranges,
            )
        )
    return parts


def merge_adjacent_segments(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    if not segments:
        return []

    ordered = sorted(segments, key=lambda item: (item.start_sec, item.end_sec))
    merged: list[CandidateSegment] = []
    buffer: list[CandidateSegment] = [ordered[0]]
    buffer_rules: list[str] = []

    for candidate in ordered[1:]:
        signals = collect_assembly_continuity_signals(buffer[-1], candidate, transcript_spans, transcript_turns, base_ranges)
        rule_family = merge_rule_family(buffer[-1], candidate, signals)
        if rule_family:
            buffer.append(candidate)
            buffer_rules.append(rule_family)
            continue
        merged.append(
            materialize_merged_segment(
                asset=asset,
                segments=buffer,
                rule_families=buffer_rules,
                transcriber=transcriber,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
            )
        )
        buffer = [candidate]
        buffer_rules = []

    merged.append(
        materialize_merged_segment(
            asset=asset,
            segments=buffer,
            rule_families=buffer_rules,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
        )
    )
    return merged


def collect_assembly_continuity_signals(
    left: CandidateSegment,
    right: CandidateSegment,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    base_ranges: list[tuple[float, float]],
) -> AssemblyContinuitySignals:
    gap_sec = round(max(0.0, right.start_sec - left.end_sec), 3)
    matching_spans = sorted(
        [
            span
            for span in transcript_spans
            if span.end_sec >= left.start_sec and span.start_sec <= right.end_sec
        ],
        key=lambda span: (span.start_sec, span.end_sec),
    )
    transcript_gap = largest_transcript_gap(matching_spans)
    matching_turns = transcript_turns_for_range(transcript_turns, left.start_sec, right.end_sec)
    transcript_turn_gap = largest_transcript_turn_gap(matching_turns)
    scene_boundaries = scene_boundaries_from_ranges(base_ranges)
    scene_divider_between = any(left.end_sec <= boundary <= right.start_sec for boundary in scene_boundaries)
    left_sources = set(left.prefilter.seed_region_sources if left.prefilter is not None else [])
    right_sources = set(right.prefilter.seed_region_sources if right.prefilter is not None else [])
    left_turn_ids = set(left.prefilter.transcript_turn_ids if left.prefilter is not None else [])
    right_turn_ids = set(right.prefilter.transcript_turn_ids if right.prefilter is not None else [])
    shared_turn = bool(left_turn_ids.intersection(right_turn_ids))
    consecutive_turns = False
    strong_turn_break_between = False
    question_answer_flow = False
    monologue_continuity = False
    if left_turn_ids and right_turn_ids and transcript_turns:
        order_by_id = {turn.id: index for index, turn in enumerate(transcript_turns)}
        left_last = max((order_by_id[turn_id] for turn_id in left_turn_ids if turn_id in order_by_id), default=-1)
        right_first = min((order_by_id[turn_id] for turn_id in right_turn_ids if turn_id in order_by_id), default=-1)
        if left_last >= 0 and right_first >= 0 and right_first - left_last == 1:
            consecutive_turns = True
            turn_gap = transcript_turns[right_first].start_sec - transcript_turns[left_last].end_sec
            strong_turn_break_between = turn_gap >= TRANSCRIPT_TURN_BREAK_GAP_SEC
    left_is_question = bool(left.transcript_excerpt.strip()) and is_question_like_text(left.transcript_excerpt)
    right_is_question = bool(right.transcript_excerpt.strip()) and is_question_like_text(right.transcript_excerpt)
    if (
        left.analysis_mode == "speech"
        and right.analysis_mode == "speech"
        and left_is_question
        and not right_is_question
        and gap_sec <= SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC
    ):
        question_answer_flow = True
    if (
        left.analysis_mode == "speech"
        and right.analysis_mode == "speech"
        and not left_is_question
        and not right_is_question
        and gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
        and not scene_divider_between
    ):
        monologue_continuity = True
    return AssemblyContinuitySignals(
        gap_sec=gap_sec,
        transcript_span_count=len(matching_spans),
        transcript_internal_gap_sec=transcript_gap,
        transcript_turn_count=len(matching_turns),
        transcript_turn_gap_sec=transcript_turn_gap,
        same_analysis_mode=left.analysis_mode == right.analysis_mode,
        shared_seed_source=bool(left_sources.intersection(right_sources)),
        scene_divider_between=scene_divider_between,
        shared_turn=shared_turn,
        consecutive_turns=consecutive_turns,
        strong_turn_break_between=strong_turn_break_between,
        question_answer_flow=question_answer_flow,
        monologue_continuity=monologue_continuity,
    )


def merge_rule_family(
    left: CandidateSegment,
    right: CandidateSegment,
    signals: AssemblyContinuitySignals,
) -> str:
    left_source_ids = assembly_source_segment_ids(left)
    right_source_ids = assembly_source_segment_ids(right)
    if (
        left.prefilter is not None
        and right.prefilter is not None
        and left.prefilter.assembly_operation == "split"
        and right.prefilter.assembly_operation == "split"
        and left_source_ids == right_source_ids
    ):
        return ""
    if signals.gap_sec > ASSEMBLY_MERGE_MAX_GAP_SEC:
        return ""
    if (
        signals.question_answer_flow
        and not signals.scene_divider_between
        and not signals.strong_turn_break_between
    ):
        return "question-answer-flow"
    if (
        signals.monologue_continuity
        and not signals.scene_divider_between
        and signals.gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
    ):
        return "monologue-continuity"
    if (
        (signals.shared_turn or signals.consecutive_turns)
        and not signals.strong_turn_break_between
        and signals.transcript_turn_gap_sec <= TRANSCRIPT_TURN_CONTINUITY_GAP_SEC
        and not signals.scene_divider_between
    ):
        return "turn-continuity"
    if (
        signals.transcript_span_count >= 2
        and signals.transcript_internal_gap_sec <= ASSEMBLY_TRANSCRIPT_CONTINUITY_GAP_SEC
        and not signals.scene_divider_between
    ):
        return "transcript-continuity"
    if (
        signals.gap_sec <= ASSEMBLY_MERGE_STRUCTURAL_GAP_SEC
        and max(left.end_sec, right.end_sec) - min(left.start_sec, right.start_sec) <= ASSEMBLY_MERGE_STRUCTURAL_MAX_DURATION_SEC
        and not signals.scene_divider_between
        and (
            signals.same_analysis_mode
            or signals.shared_seed_source
            or left.analysis_mode == "speech"
            or right.analysis_mode == "speech"
        )
    ):
        return "structural-continuity"
    return ""


def materialize_merged_segment(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    rule_families: list[str],
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
) -> CandidateSegment:
    if len(segments) == 1:
        return segments[0]

    unique_rule_families = list(dict.fromkeys(rule_families))
    rule_family = unique_rule_families[0] if len(unique_rule_families) == 1 else "continuity-chain"
    prefilters = [segment.prefilter for segment in segments if segment.prefilter is not None]
    boundary_confidence = round(
        clamp(sum(prefilter.boundary_confidence for prefilter in prefilters) / max(1, len(prefilters))),
        4,
    )

    return make_candidate_segment(
        asset=asset,
        segment_id=f"{asset.id}-merged-{segments[0].id}-{segments[-1].id}",
        start_sec=segments[0].start_sec,
        end_sec=segments[-1].end_sec,
        transcriber=transcriber,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
        boundary_strategy=f"assembly-merge:{rule_family}",
        boundary_confidence=boundary_confidence,
        seed_region_ids=flatten_prefilter_lists(segments, "seed_region_ids"),
        seed_region_sources=flatten_prefilter_lists(segments, "seed_region_sources"),
        seed_region_ranges_sec=flatten_prefilter_range_lists(segments, "seed_region_ranges_sec"),
        transcript_lookup_enabled=bool(transcript_spans),
        assembly_operation="merge",
        assembly_rule_family=rule_family,
        assembly_source_segment_ids=flatten_source_segment_ids(segments),
        assembly_source_ranges_sec=flatten_source_ranges(segments),
    )


def _find_segment_split_divider(
    segment: CandidateSegment,
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
) -> tuple[float | None, str]:
    if segment.end_sec - segment.start_sec < ASSEMBLY_SPLIT_MIN_DURATION_SEC:
        return None, ""

    matching_turns = transcript_turns_for_range(transcript_turns, segment.start_sec, segment.end_sec)
    if len(matching_turns) >= 2:
        for earlier, later in zip(matching_turns, matching_turns[1:]):
            gap_sec = later.start_sec - earlier.end_sec
            divider = round((earlier.end_sec + later.start_sec) / 2.0, 3)
            if (
                gap_sec >= TRANSCRIPT_TURN_BREAK_GAP_SEC
                and divider - segment.start_sec >= ASSEMBLY_SPLIT_MIN_PART_SEC
                and segment.end_sec - divider >= ASSEMBLY_SPLIT_MIN_PART_SEC
            ):
                return divider, "turn-break"

    matching_spans = sorted(
        [
            span
            for span in transcript_spans
            if span.end_sec >= segment.start_sec and span.start_sec <= segment.end_sec
        ],
        key=lambda span: (span.start_sec, span.end_sec),
    )
    gap_candidates: list[tuple[float, float]] = []
    for earlier, later in zip(matching_spans, matching_spans[1:]):
        gap_sec = later.start_sec - earlier.end_sec
        divider = round((earlier.end_sec + later.start_sec) / 2.0, 3)
        if (
            gap_sec >= ASSEMBLY_SPLIT_TRANSCRIPT_GAP_SEC
            and divider - segment.start_sec >= ASSEMBLY_SPLIT_MIN_PART_SEC
            and segment.end_sec - divider >= ASSEMBLY_SPLIT_MIN_PART_SEC
        ):
            gap_candidates.append((gap_sec, divider))
    if len(matching_spans) >= 3 and gap_candidates:
        _gap_sec, divider = max(gap_candidates, key=lambda item: item[0])
        return divider, "transcript-gap"

    scene_boundaries = scene_boundaries_from_ranges(base_ranges)
    eligible_boundaries = [
        boundary
        for boundary in scene_boundaries
        if segment.start_sec + ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC
        <= boundary
        <= segment.end_sec - ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC
    ]
    if not eligible_boundaries:
        return None, ""
    if matching_spans:
        for boundary in eligible_boundaries:
            has_left = any(span.start_sec < boundary for span in matching_spans)
            has_right = any(span.end_sec > boundary for span in matching_spans)
            if has_left and has_right:
                return round(boundary, 3), "scene-divider"
        return None, ""

    boundary = min(
        eligible_boundaries,
        key=lambda item: abs(item - ((segment.start_sec + segment.end_sec) / 2.0)),
    )
    return round(boundary, 3), "scene-divider"


def largest_transcript_gap(spans: list[TranscriptSpan]) -> float:
    largest_gap = 0.0
    for earlier, later in zip(spans, spans[1:]):
        largest_gap = max(largest_gap, later.start_sec - earlier.end_sec)
    return round(max(0.0, largest_gap), 3)


def largest_transcript_turn_gap(turns: list[TranscriptTurn]) -> float:
    largest_gap = 0.0
    for earlier, later in zip(turns, turns[1:]):
        largest_gap = max(largest_gap, later.start_sec - earlier.end_sec)
    return round(max(0.0, largest_gap), 3)


def scene_boundaries_from_ranges(base_ranges: list[tuple[float, float]]) -> list[float]:
    return [round(end_sec, 3) for _start_sec, end_sec in base_ranges[:-1]]


def flatten_prefilter_lists(segments: list[CandidateSegment], attribute: str) -> list[str]:
    values: list[str] = []
    for segment in segments:
        prefilter = segment.prefilter
        if prefilter is None:
            continue
        for value in getattr(prefilter, attribute):
            if value not in values:
                values.append(value)
    return values


def flatten_prefilter_range_lists(segments: list[CandidateSegment], attribute: str) -> list[list[float]]:
    values: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for segment in segments:
        prefilter = segment.prefilter
        if prefilter is None:
            continue
        for item in getattr(prefilter, attribute):
            normalized = (round(float(item[0]), 3), round(float(item[1]), 3))
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append([normalized[0], normalized[1]])
    return values


def assembly_source_segment_ids(segment: CandidateSegment) -> list[str]:
    prefilter = segment.prefilter
    if prefilter is not None and prefilter.assembly_source_segment_ids:
        return list(prefilter.assembly_source_segment_ids)
    return [segment.id]


def assembly_source_ranges_sec(segment: CandidateSegment) -> list[list[float]]:
    prefilter = segment.prefilter
    if prefilter is not None and prefilter.assembly_source_ranges_sec:
        return [list(item) for item in prefilter.assembly_source_ranges_sec]
    return [[round(segment.start_sec, 3), round(segment.end_sec, 3)]]


def flatten_source_segment_ids(segments: list[CandidateSegment]) -> list[str]:
    values: list[str] = []
    for segment in segments:
        for value in assembly_source_segment_ids(segment):
            if value not in values:
                values.append(value)
    return values


def flatten_source_ranges(segments: list[CandidateSegment]) -> list[list[float]]:
    values: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for segment in segments:
        for item in assembly_source_ranges_sec(segment):
            normalized = (round(float(item[0]), 3), round(float(item[1]), 3))
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append([normalized[0], normalized[1]])
    return values


def synthesize_quality_metrics(
    asset: Asset,
    start_sec: float,
    end_sec: float,
    analysis_mode: str,
    prefilter_snapshot: dict[str, float] | None = None,
) -> dict[str, float]:
    if prefilter_snapshot and prefilter_snapshot.get("prefilter_score", 0.0) > 0.0:
        duration = max(0.1, end_sec - start_sec)
        duration_fit = clamp(1.0 - abs(duration - 5.5) / 7.0)
        sharpness = clamp(prefilter_snapshot.get("sharpness", 0.0))
        stability = clamp(prefilter_snapshot.get("stability", 0.0))
        subject_clarity = clamp(prefilter_snapshot.get("subject_clarity", 0.0))
        motion_energy = clamp(prefilter_snapshot.get("motion_energy", 0.0))
        visual_novelty = clamp(prefilter_snapshot.get("visual_novelty", 0.0))
        prefilter_score = clamp(prefilter_snapshot.get("prefilter_score", 0.0))
        hook_strength = clamp((prefilter_score * 0.5) + (subject_clarity * 0.25) + (motion_energy * 0.25))
        story_alignment = clamp((prefilter_score * 0.45) + (visual_novelty * 0.25) + (subject_clarity * 0.2) + (duration_fit * 0.1))
        audio_energy = clamp(prefilter_snapshot.get("audio_energy", 0.0))
        speech_ratio = clamp(prefilter_snapshot.get("speech_ratio", 0.0))
        return {
            "sharpness": round(sharpness, 4),
            "stability": round(stability, 4),
            "visual_novelty": round(visual_novelty, 4),
            "subject_clarity": round(subject_clarity, 4),
            "motion_energy": round(motion_energy, 4),
            "duration_fit": round(duration_fit, 4),
            "audio_energy": round(audio_energy, 4),
            "speech_ratio": round(speech_ratio, 4),
            "hook_strength": round(hook_strength, 4),
            "story_alignment": round(story_alignment, 4),
        }

    duration = max(0.1, end_sec - start_sec)
    seed = seeded_value(asset.id, start_sec, end_sec)
    variation = seeded_value(asset.name, end_sec, start_sec)
    duration_fit = clamp(1.0 - abs(duration - 5.5) / 7.0)
    motion_energy = clamp(0.45 + seed * 0.45)
    visual_novelty = clamp(0.4 + variation * 0.5)
    subject_clarity = clamp(0.58 + seeded_value(asset.proxy_path, duration, start_sec) * 0.32)
    hook_strength = clamp(0.52 + seeded_value(asset.interchange_reel_name, end_sec, duration) * 0.38)
    story_alignment = clamp(0.55 + seeded_value(asset.source_path, start_sec, duration) * 0.35)

    return {
        "sharpness": round(clamp(0.62 + seed * 0.28), 4),
        "stability": round(clamp(0.56 + variation * 0.26), 4),
        "visual_novelty": round(visual_novelty, 4),
        "subject_clarity": round(subject_clarity, 4),
        "motion_energy": round(motion_energy, 4),
        "duration_fit": round(duration_fit, 4),
        "audio_energy": 0.0,
        "speech_ratio": 0.0,
        "hook_strength": round(hook_strength, 4),
        "story_alignment": round(story_alignment, 4),
    }


def describe_segment(
    asset: Asset,
    start_sec: float,
    end_sec: float,
    transcript_excerpt: str,
    metrics: dict[str, float],
    *,
    analysis_mode: str,
) -> str:
    duration = round(end_sec - start_sec, 2)

    if transcript_excerpt:
        return (
            f"{asset.name} yields a spoken beat around {start_sec:.2f}s to {end_sec:.2f}s. "
            f"The excerpt carries usable narrative value, and the {duration:.2f}s duration is well suited for a rough cut."
        )

    if analysis_mode == "speech":
        return (
            f"{asset.name} reads as a spoken beat from {start_sec:.2f}s to {end_sec:.2f}s, "
            f"but transcript text is unavailable. Speech activity is still strong enough to keep the {duration:.2f}s range in speech-aware scoring."
        )

    shot_role = visual_role(metrics)
    return (
        f"{asset.name} provides a {shot_role} moment from {start_sec:.2f}s to {end_sec:.2f}s. "
        f"It reads as strong silent coverage because the framing stays clear while the visual rhythm remains usable over {duration:.2f}s."
    )


def visual_role(metrics: dict[str, float]) -> str:
    if metrics["visual_novelty"] >= 0.8 and metrics["motion_energy"] >= 0.7:
        return "dynamic establishing"
    if metrics["motion_energy"] < 0.45:
        return "calm texture"
    if metrics["subject_clarity"] >= 0.8:
        return "clear detail"
    return "transition-ready"


def seeded_value(token: str, first: float, second: float) -> float:
    payload = f"{token}:{first:.3f}:{second:.3f}".encode("utf-8")
    digest = md5(payload).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF
