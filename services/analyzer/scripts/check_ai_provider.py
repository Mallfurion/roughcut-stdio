#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status, load_ai_analysis_config  # noqa: E402
from services.analyzer.app.analysis import build_transcript_provider, transcript_runtime_status  # noqa: E402


def main() -> int:
    analysis_config = load_ai_analysis_config()
    status = inspect_ai_provider_status(runtime_probe=False)
    transcript_provider = build_transcript_provider(analysis_config)
    transcript_status = transcript_runtime_status(transcript_provider)

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

    if status.configured_provider in {"lmstudio", "mlx-vlm-local"} and not status.available:
        return 1
    if analysis_config.transcript_provider == "faster-whisper" and not transcript_status.available:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
