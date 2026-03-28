from __future__ import annotations

from ..domain import Asset, CandidateSegment, SegmentEvidence


def segment_understanding_system_prompt() -> str:
    return (
        "You analyze short video segments for an editor. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Use concise editorial language and keep the response short. "
        "subjects, actions, story_roles, quality_findings, and risk_flags must each contain at most 3 short items. "
        "keep_label must be one of: keep, maybe, reject. "
        "confidence, visual_distinctiveness, clarity, and story_relevance must be numbers from 0 to 1. "
        "Keys required: summary, subjects, actions, shot_type, camera_motion, mood, "
        "story_roles, quality_findings, keep_label, confidence, rationale, risk_flags, "
        "visual_distinctiveness, clarity, story_relevance."
    )


def segment_batch_understanding_system_prompt() -> str:
    return (
        "You analyze shortlisted video segments from the same source clip for an editor. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Keep each segment result short. subjects, actions, story_roles, quality_findings, and risk_flags "
        "must each contain at most 3 short items. "
        "keep_label must be one of: keep, maybe, reject. "
        "confidence, visual_distinctiveness, clarity, and story_relevance must be numbers from 0 to 1. "
        "Respond with an object containing a `segments` array. "
        "Each array item must include: segment_id, summary, subjects, actions, shot_type, camera_motion, "
        "mood, story_roles, quality_findings, keep_label, confidence, rationale, risk_flags, "
        "visual_distinctiveness, clarity, story_relevance."
    )


def segment_understanding_user_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = transcript_prompt_text(evidence)
    keyframes = ", ".join(f"{timestamp:.2f}s" for timestamp in evidence.keyframe_timestamps_sec)

    return (
        "Project story prompt:\n"
        f"{story_prompt}\n\n"
        "Segment metadata:\n"
        f"- Asset: {asset.name}\n"
        f"- Reel: {asset.interchange_reel_name}\n"
        f"- Analysis mode: {segment.analysis_mode}\n"
        f"- Segment: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"- Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"- Keyframe timestamps: {keyframes}\n"
        f"- Metrics: {metrics}\n"
        f"- Transcript evidence: {transcript}\n\n"
        "Decide what is happening in the segment, whether it is editorially useful, "
        "what role it could play in a rough cut, and whether it should be kept."
    )


def segment_batch_understanding_user_prompt(
    *,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
) -> str:
    story_prompt = tasks[0][2] if tasks else ""
    lines = [
        "Project story prompt:",
        story_prompt,
        "",
        "Asset metadata:",
        f"- Asset: {asset.name}",
        f"- Reel: {asset.interchange_reel_name}",
        "",
        "Images are provided in the same order as the segments below. Each image is a stitched contact sheet for one segment.",
        "Evaluate each segment independently and return output for every listed segment.",
        "",
        "Segments:",
    ]
    for index, (segment, evidence, _story_prompt) in enumerate(tasks, start=1):
        metrics = ", ".join(
            f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
        )
        transcript = transcript_prompt_text(evidence)
        lines.extend(
            [
                f"{index}. segment_id={segment.id}",
                f"   - analysis_mode: {segment.analysis_mode}",
                f"   - range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s",
                f"   - context: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s",
                f"   - keyframes: {', '.join(f'{timestamp:.2f}s' for timestamp in evidence.keyframe_timestamps_sec)}",
                f"   - transcript evidence: {transcript}",
                f"   - metrics: {metrics}",
            ]
        )
    return "\n".join(lines)


def local_vlm_segment_understanding_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = transcript_prompt_text(evidence)
    return (
        "Analyze this stitched contact sheet from a shortlisted video segment and respond with exactly one compact JSON object. "
        "No markdown fences. No commentary outside JSON. No duplicated list items. "
        "Return JSON with these keys only: "
        "summary, subjects, actions, shot_type, camera_motion, mood, keep_label, confidence, rationale.\n"
        "Rules: summary and rationale must each be one short sentence with real content. "
        "subjects and actions may contain 0 to 2 short items only. "
        "shot_type must be a real label like wide, medium, close, detail, overhead, or low angle. "
        "camera_motion must be a real label like static, handheld, pan, tilt, tracking, or walking. "
        "mood must be a real label like calm, active, tense, work, or casual. "
        "keep_label must be exactly one of keep, maybe, reject. "
        "confidence must be a number between 0 and 1. "
        "If unsure, use fewer items, not more. Do not use placeholder words like short label, short sentence, item1, or item2.\n\n"
        f"Project story prompt: {story_prompt}\n"
        f"Asset: {asset.name}\n"
        f"Reel: {asset.interchange_reel_name}\n"
        f"Analysis mode: {segment.analysis_mode}\n"
        f"Segment range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"Transcript evidence: {transcript}\n"
        f"Metrics: {metrics}\n"
        "Focus on whether the segment has a clear subject, usable motion, readable composition, and editorial usefulness."
    )


def boundary_validation_system_prompt() -> str:
    return (
        "You validate whether a short video segment starts and ends at a complete editorial beat. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Keys required: decision, reason, confidence, suggested_start_sec, suggested_end_sec, split_point_sec. "
        "decision must be one of: keep, extend, trim, split. "
        "reason must be one short sentence. confidence must be a number from 0 to 1. "
        "Use null for split_point_sec unless decision is split. "
        "When decision is keep, suggested_start_sec and suggested_end_sec should match the current segment bounds."
    )


def boundary_validation_user_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = transcript_prompt_text(evidence)
    boundary_strategy = segment.prefilter.boundary_strategy if segment.prefilter is not None else "unknown"
    assembly = (
        f"{segment.prefilter.assembly_operation}:{segment.prefilter.assembly_rule_family}"
        if segment.prefilter is not None and segment.prefilter.assembly_operation != "none"
        else "none"
    )
    return (
        "Project story prompt:\n"
        f"{story_prompt}\n\n"
        "Segment metadata:\n"
        f"- Asset: {asset.name}\n"
        f"- Reel: {asset.interchange_reel_name}\n"
        f"- Analysis mode: {segment.analysis_mode}\n"
        f"- Segment: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"- Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"- Boundary strategy: {boundary_strategy}\n"
        f"- Assembly lineage: {assembly}\n"
        f"- Transcript evidence: {transcript}\n"
        f"- Metrics: {metrics}\n\n"
        "Decide whether the current segment is complete as-is, needs a small extend or trim, "
        "or contains two ideas that should be split once. Keep adjustments local to the current bounds."
    )


def local_vlm_boundary_validation_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    return (
        "Analyze this stitched contact sheet and decide whether the segment boundaries feel complete. "
        "Return exactly one compact JSON object only with keys: "
        "decision, reason, confidence. "
        "decision must be keep, extend, trim, or split. "
        "confidence must be a number between 0 and 1. reason must be one short sentence. "
        "Do not include timestamps or extra keys. "
        "Use keep when the current beat is already complete. "
        "Use trim when the beat contains extra lead-in or tail. "
        "Use extend when the beat feels cut too tight. "
        "Use split only when the contact sheet unmistakably shows two self-contained moments; "
        "if you are unsure, prefer keep. "
        "Do not use split for one continuous action that simply changes framing or composition.\n\n"
        f"Project story prompt: {story_prompt}\n"
        f"Asset: {asset.name}\n"
        f"Reel: {asset.interchange_reel_name}\n"
        f"Analysis mode: {segment.analysis_mode}\n"
        f"Segment range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"Transcript evidence: {transcript_prompt_text(evidence)}\n"
        "Focus on whether the moment starts too late, ends too early, or bundles two separate beats."
    )


def transcript_prompt_text(evidence: SegmentEvidence) -> str:
    if evidence.transcript_excerpt.strip():
        return evidence.transcript_excerpt
    if evidence.transcript_status:
        source = f" via {evidence.speech_mode_source}" if evidence.speech_mode_source else ""
        return f"No transcript excerpt available ({evidence.transcript_status}{source})."
    return "No transcript excerpt available."
