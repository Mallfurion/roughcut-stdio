from __future__ import annotations

from ..domain import CandidateSegment, SegmentReviewState
from ..shared.strings import human_join


def build_segment_review_state(segment: CandidateSegment) -> SegmentReviewState:
    prefilter = segment.prefilter
    evidence = segment.evidence_bundle
    understanding = segment.ai_understanding
    boundary_validation = segment.boundary_validation
    clip_score = None
    if prefilter is not None:
        clip_score = prefilter.metrics_snapshot.get("clip_score")

    model_analyzed = bool(understanding and understanding.provider != "deterministic")
    deterministic_fallback = bool(understanding and understanding.provider == "deterministic")
    evidence_keyframe_count = len(evidence.keyframe_timestamps_sec) if evidence is not None else 0
    blocked_reason = review_blocked_reason(segment)
    transcript_status = evidence.transcript_status if evidence is not None else default_segment_transcript_status(segment)
    speech_mode_source = evidence.speech_mode_source if evidence is not None else default_segment_speech_mode_source(segment)

    return SegmentReviewState(
        shortlisted=bool(prefilter and prefilter.shortlisted),
        filtered_before_vlm=bool(prefilter and prefilter.filtered_before_vlm),
        clip_scored=clip_score is not None,
        clip_score=round(clip_score, 4) if clip_score is not None else None,
        clip_gated=bool(prefilter and prefilter.clip_gated),
        deduplicated=bool(prefilter and prefilter.deduplicated),
        dedup_group_id=prefilter.dedup_group_id if prefilter is not None else None,
        vlm_budget_capped=bool(prefilter and prefilter.vlm_budget_capped),
        model_analyzed=model_analyzed,
        deterministic_fallback=deterministic_fallback,
        evidence_keyframe_count=evidence_keyframe_count,
        analysis_path_summary=describe_analysis_path(segment, evidence_keyframe_count),
        blocked_reason=blocked_reason,
        boundary_strategy_label=boundary_strategy_label(segment),
        boundary_confidence=round(prefilter.boundary_confidence, 4) if prefilter is not None else None,
        lineage_summary=lineage_summary(segment),
        semantic_validation_status=boundary_validation.status if boundary_validation is not None else "",
        semantic_validation_summary=semantic_validation_summary(segment),
        transcript_status=transcript_status,
        transcript_summary=transcript_summary(segment, transcript_status, speech_mode_source),
        speech_mode_source=speech_mode_source,
        turn_summary=turn_summary(segment),
        speech_structure_summary=speech_structure_summary(segment),
    )


def describe_analysis_path(segment: CandidateSegment, evidence_keyframe_count: int) -> str:
    prefilter = segment.prefilter
    understanding = segment.ai_understanding
    boundary_validation = segment.boundary_validation
    steps: list[str] = []

    if prefilter and prefilter.shortlisted:
        steps.append("shortlisted")
    else:
        steps.append("screened locally only")

    clip_score = prefilter.metrics_snapshot.get("clip_score") if prefilter is not None else None
    if clip_score is not None:
        steps.append(f"CLIP {round(clip_score * 100):d}")
    if prefilter and prefilter.deduplicated:
        steps.append(f"deduped in group {prefilter.dedup_group_id}")
    if prefilter and prefilter.assembly_operation != "none":
        rule_label = prefilter.assembly_rule_family or prefilter.assembly_operation
        steps.append(f"{prefilter.assembly_operation} via {rule_label}")
    if prefilter and prefilter.clip_gated:
        steps.append("CLIP gated")
    if prefilter and prefilter.vlm_budget_capped:
        steps.append("budget capped")
    if boundary_validation is not None:
        if boundary_validation.status == "validated":
            steps.append(f"boundary {boundary_validation.decision}")
        elif boundary_validation.status == "fallback":
            steps.append("boundary fallback")
        elif boundary_validation.status == "skipped":
            steps.append(f"boundary skipped ({boundary_validation.skip_reason})")
    if evidence_keyframe_count > 0:
        steps.append(f"{evidence_keyframe_count} keyframe{'s' if evidence_keyframe_count != 1 else ''}")
    elif segment.analysis_mode == "speech" and not segment.transcript_excerpt.strip():
        steps.append("speech fallback")

    if understanding is not None:
        if understanding.provider == "deterministic":
            steps.append("deterministic fallback")
        else:
            steps.append(f"VLM {understanding.provider}")

    return " -> ".join(steps)


def default_segment_transcript_status(segment: CandidateSegment) -> str:
    if segment.transcript_excerpt.strip():
        return "excerpt-available"
    if segment.analysis_mode == "speech":
        return "fallback-no-transcript"
    return "not-applicable"


def default_segment_speech_mode_source(segment: CandidateSegment) -> str:
    if segment.transcript_excerpt.strip():
        return "transcript"
    if segment.analysis_mode == "speech":
        return "speech-signal-fallback"
    return "visual"


def transcript_summary(segment: CandidateSegment, transcript_status: str, speech_mode_source: str) -> str:
    if transcript_status == "excerpt-available":
        prefilter = segment.prefilter
        if prefilter is not None and prefilter.transcript_turn_ids:
            return (
                f"Transcript excerpt available with {len(prefilter.transcript_turn_ids)} aligned "
                f"turn{'s' if len(prefilter.transcript_turn_ids) != 1 else ''}."
            )
        return "Transcript excerpt available for this segment."
    if transcript_status == "selective-skip":
        return "Transcript extraction was skipped for this asset because cheap speech signals stayed below the selective-transcription threshold."
    if transcript_status == "fallback-no-transcript":
        source_label = speech_mode_source or "speech-signal-fallback"
        return f"Speech-aware fallback is active because transcript text is unavailable ({source_label})."
    if transcript_status in {"provider-disabled", "provider-unavailable", "provider-partial"}:
        return f"Transcript support did not provide excerpt text ({transcript_status})."
    if segment.analysis_mode == "speech":
        return "Speech scoring is active without transcript text."
    return "No transcript evidence was needed for this segment."


def review_blocked_reason(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    if prefilter.deduplicated:
        return "duplicate"
    if prefilter.clip_gated:
        return "clip_gate"
    if prefilter.vlm_budget_capped:
        return "budget_cap"
    if prefilter.filtered_before_vlm:
        return "shortlist_filter"
    return ""


def boundary_strategy_label(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    strategy = prefilter.boundary_strategy
    labels = {
        "legacy": "Legacy window",
        "turn-snap": "Turn snapped",
        "transcript-snap": "Transcript snapped",
        "audio-snap": "Audio snapped",
        "scene-snap": "Scene snapped",
        "scene-duration": "Scene duration rule",
        "duration-rule": "Duration rule",
    }
    if strategy in labels:
        return labels[strategy]
    if strategy.startswith("assembly-merge:"):
        rule = strategy.split(":", 1)[1].replace("-", " ")
        return f"Assembly merged ({rule})"
    if strategy.startswith("assembly-split:"):
        rule = strategy.split(":", 1)[1].replace("-", " ")
        return f"Assembly split ({rule})"
    return strategy.replace("-", " ").title()


def lineage_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    if prefilter.assembly_operation == "merge" and prefilter.assembly_source_segment_ids:
        count = len(prefilter.assembly_source_segment_ids)
        rule = prefilter.assembly_rule_family.replace("-", " ") if prefilter.assembly_rule_family else "continuity"
        return f"Merged {count} refined regions via {rule}."
    if prefilter.assembly_operation == "split" and prefilter.assembly_source_segment_ids:
        source_id = prefilter.assembly_source_segment_ids[0]
        rule = prefilter.assembly_rule_family.replace("-", " ") if prefilter.assembly_rule_family else "internal divider"
        return f"Split from {source_id} via {rule}."
    if prefilter.seed_region_ids:
        count = len(prefilter.seed_region_ids)
        sources = human_join([value.replace("-", " ") for value in prefilter.seed_region_sources[:3]])
        return f"Built from {count} seed region{'s' if count != 1 else ''} ({sources})."
    return ""


def turn_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.transcript_turn_ids:
        return ""
    count = len(prefilter.transcript_turn_ids)
    if prefilter.assembly_rule_family == "turn-continuity":
        return f"Merged {count} transcript turns via turn continuity."
    if prefilter.assembly_rule_family == "question-answer-flow":
        return "Merged across a question/answer flow."
    if prefilter.assembly_rule_family == "monologue-continuity":
        return "Merged across continuous monologue flow."
    if prefilter.assembly_rule_family == "turn-break":
        return "Split at a strong transcript turn break."
    alignment = prefilter.transcript_turn_alignment or "turn-aware"
    if alignment == "turn-aligned":
        return f"Aligned to {count} transcript turn{'s' if count != 1 else ''}."
    if alignment == "mostly-complete":
        return f"Mostly covers {count} transcript turn{'s' if count != 1 else ''}."
    return f"Partially overlaps {count} transcript turn{'s' if count != 1 else ''}."


def speech_structure_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.speech_structure_label:
        return ""
    label = prefilter.speech_structure_label.replace("-", " ")
    if prefilter.speech_structure_cues:
        cues = human_join([cue.replace("_", " ") for cue in prefilter.speech_structure_cues[:3]])
        return f"Speech structure reads as {label} ({cues})."
    return f"Speech structure reads as {label}."


def semantic_validation_summary(segment: CandidateSegment) -> str:
    validation = segment.boundary_validation
    if validation is None:
        return ""
    target_prefix = ""
    if validation.target_reason == "floor":
        target_prefix = "Floor-targeted semantic validation "
    if validation.status == "validated":
        if validation.decision == "keep":
            return f"{target_prefix or 'Semantic validation '}kept the deterministic boundary at {round(validation.confidence * 100):d}% confidence."
        if validation.decision == "split":
            return f"{target_prefix or 'Semantic validation '}split the segment because {validation.reason.lower()}"
        return f"{target_prefix or 'Semantic validation '}suggested {validation.decision} because {validation.reason.lower()}"
    if validation.status == "fallback":
        return "Semantic validation fell back to deterministic output."
    if validation.status == "skipped":
        reason = validation.skip_reason.replace("_", " ") if validation.skip_reason else "not run"
        return f"Semantic validation skipped: {reason}."
    if validation.status == "not_eligible":
        return validation.reason
    return ""
