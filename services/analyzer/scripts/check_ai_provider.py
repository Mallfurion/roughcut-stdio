#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status  # noqa: E402


def main() -> int:
    status = inspect_ai_provider_status(runtime_probe=True)

    print(f"configured_provider: {status.configured_provider}")
    print(f"effective_provider: {status.effective_provider}")
    print(f"model: {status.model or '(none)'}")
    print(f"revision: {status.revision or '(none)'}")
    print(f"cache_dir: {status.cache_dir or '(none)'}")
    print(f"device: {status.device or '(none)'}")
    print(f"base_url: {status.base_url}")
    print(f"available: {'yes' if status.available else 'no'}")
    print(f"detail: {status.detail}")

    if status.configured_provider in {"lmstudio", "mlx-vlm-local"} and not status.available:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
