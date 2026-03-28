from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ..domain import Asset, BoundaryValidationResult, CandidateSegment, SegmentEvidence, SegmentUnderstanding

PLACEHOLDER_TEXT_VALUES = {
    "short label",
    "short sentence",
    "item1",
    "item2",
    "item 1",
    "item 2",
    "label",
    "sentence",
    "n/a",
    "none",
    "null",
    "placeholder",
}


class FallbackAnalyzer(Protocol):
    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        ...


def normalize_boundary_validation_output(
    payload: dict[str, object],
    *,
    provider: str,
    model: str,
    segment: CandidateSegment,
    asset: Asset | None = None,
) -> BoundaryValidationResult:
    decision_raw = str(payload.get("decision", "keep")).strip().lower()
    decision = decision_raw if decision_raw in {"keep", "extend", "trim", "split"} else "keep"
    reason = string_or_default(payload.get("reason"), "Semantic validation kept the deterministic boundary.")
    confidence = rounded_metric(number_or_default(payload.get("confidence"), 0.0))
    if provider == "mlx-vlm-local" and decision == "split" and confidence < 0.85:
        decision = "keep"
        reason = (
            "Semantic validation kept the deterministic boundary because the local split recommendation "
            "was not confident enough."
        )
    segment_duration = max(0.0, segment.end_sec - segment.start_sec)
    local_delta = round(min(0.75, max(0.25, segment_duration * 0.12)), 3)
    asset_duration = asset.duration_sec if asset is not None else segment.end_sec

    default_start_sec = segment.start_sec
    default_end_sec = segment.end_sec
    if decision == "trim":
        default_start_sec = min(segment.end_sec - 1.5, segment.start_sec + local_delta)
        default_end_sec = max(default_start_sec + 1.5, segment.end_sec - local_delta)
    elif decision == "extend":
        default_start_sec = max(0.0, segment.start_sec - local_delta)
        default_end_sec = min(asset_duration, segment.end_sec + local_delta)

    suggested_start_sec = round(float(number_or_default(payload.get("suggested_start_sec"), default_start_sec)), 3)
    suggested_end_sec = round(float(number_or_default(payload.get("suggested_end_sec"), default_end_sec)), 3)
    split_point_sec = payload.get("split_point_sec")
    split_ranges_sec: list[list[float]] = []
    if decision == "split":
        split_point = number_or_default(split_point_sec, (segment.start_sec + segment.end_sec) / 2.0)
        split_ranges_sec = [
            [round(segment.start_sec, 3), round(split_point, 3)],
            [round(split_point, 3), round(segment.end_sec, 3)],
        ]

    return BoundaryValidationResult(
        status="validated",
        decision=decision,
        reason=reason,
        confidence=confidence,
        provider=provider,
        provider_model=model,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(suggested_start_sec, 3), round(suggested_end_sec, 3)],
        split_ranges_sec=split_ranges_sec,
    )


def boundary_validation_fallback_result(
    *,
    segment: CandidateSegment,
    detail: str,
    provider: str = "deterministic",
    model: str = "fallback-v1",
    skip_reason: str = "request_failed",
) -> BoundaryValidationResult:
    return BoundaryValidationResult(
        status="fallback",
        decision="keep",
        reason=f"Semantic boundary validation fell back to deterministic output: {detail}",
        confidence=0.0,
        provider=provider,
        provider_model=model,
        skip_reason=skip_reason,
        applied=False,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
    )


def extract_generation_text(result: Any) -> str:
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(result).strip()


def normalize_model_output(
    payload: dict[str, object],
    *,
    provider: str,
    model: str,
    fallback: FallbackAnalyzer,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> SegmentUnderstanding:
    fallback_understanding = fallback.analyze(
        asset=asset,
        segment=segment,
        evidence=evidence,
        story_prompt=story_prompt,
    )

    return SegmentUnderstanding(
        provider=provider,
        provider_model=model,
        schema_version=str(payload.get("schema_version", "segment-understanding-v1")),
        summary=string_or_default(payload.get("summary"), fallback_understanding.summary),
        subjects=list_or_default(payload.get("subjects"), fallback_understanding.subjects),
        actions=list_or_default(payload.get("actions"), fallback_understanding.actions),
        shot_type=string_or_default(payload.get("shot_type"), fallback_understanding.shot_type),
        camera_motion=string_or_default(payload.get("camera_motion"), fallback_understanding.camera_motion),
        mood=string_or_default(payload.get("mood"), fallback_understanding.mood),
        story_roles=list_or_default(payload.get("story_roles"), fallback_understanding.story_roles),
        quality_findings=list_or_default(
            payload.get("quality_findings"),
            fallback_understanding.quality_findings,
        ),
        keep_label=keep_label_or_default(payload.get("keep_label"), fallback_understanding.keep_label),
        confidence=rounded_metric(number_or_default(payload.get("confidence"), fallback_understanding.confidence)),
        rationale=string_or_default(payload.get("rationale"), fallback_understanding.rationale),
        risk_flags=list_or_default(payload.get("risk_flags"), fallback_understanding.risk_flags),
        visual_distinctiveness=rounded_metric(
            number_or_default(payload.get("visual_distinctiveness"), fallback_understanding.visual_distinctiveness)
        ),
        clarity=rounded_metric(number_or_default(payload.get("clarity"), fallback_understanding.clarity)),
        story_relevance=rounded_metric(
            number_or_default(payload.get("story_relevance"), fallback_understanding.story_relevance)
        ),
    )


def normalize_batch_model_output(
    *,
    payload: dict[str, object],
    provider: str,
    model: str,
    fallback: FallbackAnalyzer,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
) -> dict[str, SegmentUnderstanding]:
    items = payload.get("segments", [])
    by_segment_id = {
        str(item.get("segment_id", "")).strip(): item
        for item in items
        if isinstance(item, dict)
    } if isinstance(items, list) else {}

    normalized: dict[str, SegmentUnderstanding] = {}
    for segment, evidence, story_prompt in tasks:
        item = by_segment_id.get(segment.id)
        if item is None:
            understanding = fallback.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            understanding.risk_flags = sorted(set([*understanding.risk_flags, "lmstudio_incomplete_batch_result"]))
            understanding.rationale = (
                f"{understanding.rationale} LM Studio batch response did not include this segment, "
                "so deterministic fallback was used."
            )
        else:
            understanding = normalize_model_output(
                item,
                provider=provider,
                model=model,
                fallback=fallback,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
        normalized[segment.id] = understanding
    return normalized


def parse_json_object(raw: str) -> dict[str, object] | None:
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return salvage_partial_json_object(raw)
        try:
            loaded = json.loads(match.group(0))
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            return salvage_partial_json_object(match.group(0))


def parse_key_value_object(
    raw: str,
    *,
    allowed_keys: set[str] | None = None,
) -> dict[str, object] | None:
    payload: dict[str, object] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        if not normalized_key:
            continue
        if allowed_keys is not None and normalized_key not in allowed_keys:
            continue
        parsed_value: object = value.strip()
        if isinstance(parsed_value, str):
            if parsed_value.startswith('"') and parsed_value.endswith('"') and len(parsed_value) >= 2:
                parsed_value = parsed_value[1:-1]
            else:
                lowered = parsed_value.lower()
                if lowered == "null":
                    parsed_value = None
                else:
                    try:
                        parsed_value = int(parsed_value)
                    except ValueError:
                        try:
                            parsed_value = float(parsed_value)
                        except ValueError:
                            parsed_value = parsed_value
        payload[normalized_key] = parsed_value
    return payload or None


def salvage_partial_json_object(raw: str) -> dict[str, object] | None:
    start = raw.find("{")
    if start < 0:
        return None

    candidate = raw[start:].rstrip()
    while candidate:
        try:
            loaded = json.loads(candidate)
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            last_comma = candidate.rfind(",")
            if last_comma < 0:
                break
            candidate = close_partial_json(candidate[:last_comma].rstrip())

    return None


def close_partial_json(raw: str) -> str:
    output: list[str] = []
    closers: list[str] = []
    in_string = False
    escaped = False

    for char in raw:
        output.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            closers.append("}")
        elif char == "[":
            closers.append("]")
        elif char in {"]", "}"} and closers and closers[-1] == char:
            closers.pop()

    if in_string:
        output.append('"')

    while closers:
        output.append(closers.pop())

    return "".join(output)


def string_or_default(value: object, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned and not looks_like_placeholder_text(cleaned):
            return cleaned
    return default


def list_or_default(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        seen: set[str] = set()
        for item in value:
            cleaned = str(item).strip()
            if not cleaned or looks_like_placeholder_text(cleaned):
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(cleaned)
        if items:
            return items
    return default


def keep_label_or_default(value: object, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"keep", "maybe", "reject"}:
            return cleaned
    return default


def looks_like_placeholder_text(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    if not normalized:
        return True
    if normalized in PLACEHOLDER_TEXT_VALUES:
        return True
    if normalized.startswith("short "):
        return True
    return bool(re.fullmatch(r"item\s*\d+", normalized))


def number_or_default(value: object, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def rounded_metric(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
