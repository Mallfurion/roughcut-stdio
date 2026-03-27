#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.analysis import FasterWhisperAdapter, build_transcript_provider, load_ai_analysis_config  # noqa: E402


def main() -> int:
    config = load_ai_analysis_config()
    provider = build_transcript_provider(config)
    status = provider.runtime_status()
    print(f"configured_provider: {status.configured_provider}")
    print(f"effective_provider: {status.effective_provider}")
    print(f"model_size: {status.model_size or '(none)'}")
    print(f"enabled: {'yes' if status.enabled else 'no'}")
    print(f"available: {'yes' if status.available else 'no'}")
    print(f"status: {status.status}")
    print(f"detail: {status.detail}")

    if not status.enabled:
        print("Transcript runtime is disabled; nothing to bootstrap.")
        return 0

    if status.effective_provider != "faster-whisper":
        print("Transcript runtime is not backed by faster-whisper; skipping bootstrap.")
        return 0

    if not isinstance(provider, FasterWhisperAdapter):
        print("Transcript runtime adapter is not bootstrappable.")
        return 1

    if provider._ensure_model_loaded():  # noqa: SLF001
        bootstrapped = provider.runtime_status()
        print(
            "Bootstrapped transcript model "
            f"{bootstrapped.model_size or '(none)'} on "
            f"{bootstrapped.effective_provider}."
        )
        return 0

    failed = provider.runtime_status()
    print(f"Failed to bootstrap transcript runtime: {failed.detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
