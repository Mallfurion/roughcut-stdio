#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status, load_ai_analysis_config  # noqa: E402
from services.analyzer.app.analysis import (  # noqa: E402
    build_transcript_provider,
    combined_runtime_status_label,
    runtime_status_label,
    transcript_runtime_status,
)


def main() -> int:
    analysis_config = load_ai_analysis_config()
    status = inspect_ai_provider_status(runtime_probe=False)
    transcript_provider = build_transcript_provider(analysis_config)
    transcript_status = transcript_runtime_status(transcript_provider)
    ai_runtime_mode = runtime_status_label(
        active=status.available,
        unavailable=not status.available,
        fallback_count=0,
        skipped_count=0,
    )
    transcript_runtime_mode = runtime_status_label(
        active=transcript_status.enabled and transcript_status.available,
        unavailable=transcript_status.enabled and not transcript_status.available,
        fallback_count=transcript_status.failed_asset_count,
        skipped_count=transcript_status.probe_rejected_asset_count,
    )
    semantic_runtime_mode = runtime_status_label(
        active=analysis_config.semantic_boundary_validation_enabled,
        unavailable=analysis_config.semantic_boundary_validation_enabled and not status.available,
        fallback_count=0,
        skipped_count=0,
    )
    cache_runtime_mode = runtime_status_label(
        active=analysis_config.cache_enabled,
        unavailable=False,
        fallback_count=0,
        skipped_count=0,
    )
    degraded_reasons: list[str] = []
    intentional_skip_reasons: list[str] = []
    if not status.available:
        degraded_reasons.append("AI provider unavailable")
    if transcript_status.enabled and not transcript_status.available:
        degraded_reasons.append("transcript runtime unavailable")
    if not transcript_status.enabled:
        intentional_skip_reasons.append("transcript provider disabled")
    if not analysis_config.semantic_boundary_validation_enabled:
        intentional_skip_reasons.append("semantic boundary validation disabled")
    if not analysis_config.cache_enabled:
        intentional_skip_reasons.append("AI cache disabled")
    runtime_reliability_mode = combined_runtime_status_label(
        ai_runtime_mode,
        transcript_runtime_mode,
        semantic_runtime_mode,
        cache_runtime_mode,
    )
    runtime_summary = (
        f"AI {ai_runtime_mode}, "
        f"transcript {transcript_runtime_mode}, "
        f"semantic {semantic_runtime_mode}, "
        f"cache {cache_runtime_mode}"
    )
    runtime_ready = runtime_reliability_mode not in {"inactive", "unavailable"}

    print(f"configured_provider: {status.configured_provider}")
    print(f"effective_provider: {status.effective_provider}")
    print(f"model: {status.model or '(none)'}")
    print(f"revision: {status.revision or '(none)'}")
    print(f"cache_dir: {status.cache_dir or '(none)'}")
    print(f"device: {status.device or '(none)'}")
    print(f"base_url: {status.base_url}")
    print(f"available: {'yes' if status.available else 'no'}")
    print(f"detail: {status.detail}")
    print(f"transcript_provider_configured: {analysis_config.transcript_provider}")
    print(f"transcript_provider_effective: {transcript_status.effective_provider}")
    print(f"transcript_model_size: {analysis_config.transcript_model_size}")
    print(f"transcript_enabled: {'yes' if transcript_status.enabled else 'no'}")
    print(f"transcript_available: {'yes' if transcript_status.available else 'no'}")
    print(f"transcript_status: {transcript_status.status}")
    print(f"transcript_detail: {transcript_status.detail}")
    print(f"runtime_ready: {'yes' if runtime_ready else 'no'}")
    print(f"runtime_reliability_mode: {runtime_reliability_mode}")
    print(f"ai_runtime_mode: {ai_runtime_mode}")
    print(f"transcript_runtime_mode: {transcript_runtime_mode}")
    print(f"semantic_boundary_runtime_mode: {semantic_runtime_mode}")
    print(f"cache_runtime_mode: {cache_runtime_mode}")
    print(f"degraded: {'yes' if bool(degraded_reasons) else 'no'}")
    print(f"runtime_summary: {runtime_summary}")
    print(f"degraded_reasons: {' | '.join(degraded_reasons) if degraded_reasons else '(none)'}")
    print(
        "intentional_skip_reasons: "
        + (" | ".join(intentional_skip_reasons) if intentional_skip_reasons else "(none)")
    )

    if status.configured_provider in {"lmstudio", "mlx-vlm-local"} and not status.available:
        return 1
    if analysis_config.transcript_provider == "faster-whisper" and not transcript_status.available:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
