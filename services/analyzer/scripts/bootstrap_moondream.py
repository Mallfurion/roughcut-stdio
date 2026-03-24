#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import bootstrap_moondream_model, load_ai_provider_config  # noqa: E402


def main() -> int:
    config = load_ai_provider_config()
    if config.provider != "moondream-local":
        print("Moondream bootstrap skipped because TIMELINE_AI_PROVIDER is not moondream-local.")
        return 0

    status = bootstrap_moondream_model(config)
    print(f"configured_provider: {status.configured_provider}")
    print(f"effective_provider: {status.effective_provider}")
    print(f"model: {status.model or '(none)'}")
    print(f"revision: {status.revision or '(none)'}")
    print(f"cache_dir: {status.cache_dir or '(none)'}")
    print(f"device: {status.device or '(none)'}")
    print(f"available: {'yes' if status.available else 'no'}")
    print(f"detail: {status.detail}")
    return 0 if status.available else 1


if __name__ == "__main__":
    raise SystemExit(main())
