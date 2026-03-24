#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status  # noqa: E402
from services.analyzer.app.domain import Asset  # noqa: E402
from services.analyzer.app.service import scan_and_analyze_media_root  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: scan_media_root.py <project-name> <media-root> [story-prompt]\n")
        return 1

    project_name = sys.argv[1]
    media_root = sys.argv[2]
    story_prompt = sys.argv[3] if len(sys.argv) > 3 else "Build a coherent rough cut."
    start_time = time.monotonic()

    provider_status = inspect_ai_provider_status()
    log_to_stderr(f"Media root: {media_root}")
    log_to_stderr(
        f"AI provider configured: {provider_status.configured_provider or 'deterministic'}"
        + (f" ({provider_status.model})" if provider_status.model else "")
    )
    log_to_stderr(provider_status.detail)

    def status_callback(message: str) -> None:
        log_to_stderr(message)

    def progress_callback(processed: int, total: int, asset: Asset) -> None:
        render_progress(processed, total, asset.name, start_time)

    project = scan_and_analyze_media_root(
        project_name=project_name,
        media_roots=[media_root],
        story_prompt=story_prompt,
        artifacts_root=ROOT / "generated" / "analysis",
        status_callback=status_callback,
        progress_callback=progress_callback,
    )
    if not project.assets:
        log_to_stderr("No source assets were available to process.")
    sys.stdout.write(__import__("json").dumps(project.to_dict(), indent=2))
    return 0


def render_progress(
    processed: int,
    total: int,
    asset_name: str,
    start_time: float,
    finished: bool = False,
) -> None:
    total = max(total, 1)
    width = 28
    ratio = min(1.0, max(0.0, processed / total))
    filled = int(round(width * ratio))
    bar = "=" * filled + "." * (width - filled)
    elapsed = max(0.0, time.monotonic() - start_time)
    eta = (elapsed / processed) * (total - processed) if processed > 0 else 0.0
    message = (
        f"[{bar}] {processed}/{total} assets"
        f" | elapsed {format_clock(elapsed)}"
        f" | eta {format_clock(eta)}"
        f" | {asset_name[:42]}"
    )

    if sys.stderr.isatty():
        sys.stderr.write("\r" + message.ljust(120))
        if finished or processed >= total:
            sys.stderr.write("\n")
    else:
        sys.stderr.write(message + "\n")
    sys.stderr.flush()


def format_clock(value: float) -> str:
    total_seconds = int(round(max(0.0, value)))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def log_to_stderr(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


if __name__ == "__main__":
    raise SystemExit(main())
