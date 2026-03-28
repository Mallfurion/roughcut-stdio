from __future__ import annotations

from dataclasses import asdict
from hashlib import sha1
import json
from pathlib import Path

from ..domain import Asset, CandidateSegment, SegmentEvidence, SegmentUnderstanding

SCHEMA_VERSION = "segment-understanding-v1"


def load_cached_understanding(cache_root: Path | None, cache_key: str) -> SegmentUnderstanding | None:
    if cache_root is None:
        return None
    target = cache_root / f"{cache_key}.json"
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return SegmentUnderstanding(**payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def store_cached_understanding(cache_root: Path | None, cache_key: str, understanding: SegmentUnderstanding) -> None:
    if cache_root is None:
        return
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"{cache_key}.json"
    try:
        payload = asdict(understanding) if hasattr(understanding, "__dataclass_fields__") else dict(understanding)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def build_segment_cache_key(
    *,
    model: str,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "asset_id": asset.id,
        "asset_path": asset.proxy_path,
        "segment_id": segment.id,
        "segment_range": [segment.start_sec, segment.end_sec],
        "analysis_mode": segment.analysis_mode,
        "transcript_excerpt": evidence.transcript_excerpt,
        "story_prompt": story_prompt,
        "keyframe_timestamps_sec": evidence.keyframe_timestamps_sec,
    }
    return sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
