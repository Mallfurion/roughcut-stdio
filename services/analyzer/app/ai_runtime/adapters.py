from __future__ import annotations

from pathlib import Path
from typing import Any

from .cache import build_segment_cache_key, load_cached_understanding, store_cached_understanding
from .config import AIRuntimeStats
from ..domain import Asset, CandidateSegment, SegmentEvidence, SegmentUnderstanding

PendingAnalysisTask = tuple[CandidateSegment, SegmentEvidence, str, str]


class CachedFallbackAdapter:
    def __init__(
        self,
        *,
        model: str,
        fallback: Any,
        cache_root: str | Path | None = None,
    ) -> None:
        self._adapter_model = model
        self.fallback = fallback
        self.last_error_detail = ""
        self.cache_root = Path(cache_root) if cache_root is not None else None
        self._runtime_stats = AIRuntimeStats()

    def _prepare_cached_request(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> tuple[str, SegmentUnderstanding | None]:
        cache_key = build_segment_cache_key(
            model=self._adapter_model,
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        cached = load_cached_understanding(self.cache_root, cache_key)
        if cached is not None:
            self._runtime_stats.cached_segment_count += 1
        return cache_key, cached

    def _collect_pending_tasks(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> tuple[dict[str, SegmentUnderstanding], list[PendingAnalysisTask]]:
        results: dict[str, SegmentUnderstanding] = {}
        pending: list[PendingAnalysisTask] = []

        for segment, evidence, story_prompt in tasks:
            cache_key, cached = self._prepare_cached_request(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            if cached is not None:
                results[segment.id] = cached
            else:
                pending.append((segment, evidence, story_prompt, cache_key))

        return results, pending

    def _record_understanding(
        self,
        *,
        cache_key: str,
        understanding: SegmentUnderstanding,
        live_provider: str,
    ) -> SegmentUnderstanding:
        if understanding.provider == live_provider:
            self._runtime_stats.live_segment_count += 1
        else:
            self._runtime_stats.fallback_segment_count += 1
        store_cached_understanding(self.cache_root, cache_key, understanding)
        return understanding

    def _make_fallback_understanding(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
        detail: str,
        risk_flag: str,
        failure_label: str,
    ) -> SegmentUnderstanding:
        fallback = self.fallback.analyze(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        fallback.provider = "deterministic"
        fallback.provider_model = "fallback-v1"
        fallback.risk_flags = sorted(set([*fallback.risk_flags, risk_flag]))
        fallback.rationale = f"{fallback.rationale} {failure_label}: {detail}"
        return fallback

    def _record_live_request(self) -> None:
        self._runtime_stats.live_request_count += 1

    def _record_fallback_result(self) -> None:
        self._runtime_stats.fallback_segment_count += 1

    def runtime_stats(self) -> AIRuntimeStats:
        return AIRuntimeStats(
            live_segment_count=self._runtime_stats.live_segment_count,
            cached_segment_count=self._runtime_stats.cached_segment_count,
            fallback_segment_count=self._runtime_stats.fallback_segment_count,
            live_request_count=self._runtime_stats.live_request_count,
        )
