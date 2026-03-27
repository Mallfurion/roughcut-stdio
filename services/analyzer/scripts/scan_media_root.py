#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status, load_ai_analysis_config  # noqa: E402
from services.analyzer.app.domain import Asset  # noqa: E402
from services.analyzer.app.service import scan_and_analyze_media_root  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("media_root")
    parser.add_argument("story_prompt", nargs="?", default="Build a coherent rough cut.")
    parser.add_argument("--artifacts-root", default=str(ROOT / "generated" / "analysis"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_name = args.project_name
    media_root = args.media_root
    story_prompt = args.story_prompt
    artifacts_root = Path(args.artifacts_root).resolve()
    start_time = time.monotonic()

    provider_status = inspect_ai_provider_status()
    analysis_config = load_ai_analysis_config()
    log_to_stderr(f"Media root: {media_root}")
    log_to_stderr(
        f"AI provider configured: {provider_status.configured_provider or 'deterministic'}"
        + (f" ({provider_status.model})" if provider_status.model else "")
    )
    if provider_status.revision:
        log_to_stderr(f"AI model revision: {provider_status.revision}")
    if provider_status.cache_dir:
        log_to_stderr(f"AI model cache: {provider_status.cache_dir}")
    if provider_status.device:
        log_to_stderr(f"AI requested device: {provider_status.device}")
    log_to_stderr(provider_status.detail)
    log_to_stderr(
        "AI runtime mode: "
        f"{analysis_config.mode}, "
        f"shortlist={analysis_config.max_segments_per_asset}/asset, "
        f"keyframes={analysis_config.max_keyframes_per_segment}, "
        f"width={analysis_config.keyframe_max_width}px, "
        f"concurrency={analysis_config.concurrency}, "
        f"cache={'on' if analysis_config.cache_enabled else 'off'}"
    )
    log_to_stderr(
        "Transcript runtime: "
        f"provider={analysis_config.transcript_provider}, "
        f"model_size={analysis_config.transcript_model_size}"
    )

    def status_callback(message: str) -> None:
        log_to_stderr(message)

    def progress_callback(processed: int, total: int, asset: Asset) -> None:
        render_progress(processed, total, asset.name, start_time)

    project = scan_and_analyze_media_root(
        project_name=project_name,
        media_roots=[media_root],
        story_prompt=story_prompt,
        artifacts_root=artifacts_root,
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
