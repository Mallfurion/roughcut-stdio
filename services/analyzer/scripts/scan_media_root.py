#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai import inspect_ai_provider_status, load_ai_analysis_config  # noqa: E402
from services.analyzer.app.domain import Asset  # noqa: E402
from services.analyzer.app.process_reporting import ProcessConsoleProxy, ProcessReporter  # noqa: E402
from services.analyzer.app.service import scan_and_analyze_media_root  # noqa: E402

ANALYZE_RE = re.compile(r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+Analyzing:\s+(?P<asset>.+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("media_root")
    parser.add_argument("story_prompt", nargs="?", default="Build a coherent rough cut.")
    parser.add_argument("--artifacts-root", default=str(ROOT / "generated" / "analysis"))
    parser.add_argument("--process-output-file", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_name = args.project_name
    media_root = args.media_root
    story_prompt = args.story_prompt
    artifacts_root = Path(args.artifacts_root).resolve()
    start_time = time.monotonic()
    console_stream = sys.stderr
    reporter = ProcessReporter(artifact_path=args.process_output_file or None, console_stream=console_stream)
    stderr_proxy = ProcessConsoleProxy(stream=console_stream, reporter=reporter)

    provider_status = inspect_ai_provider_status()
    analysis_config = load_ai_analysis_config()
    emit_preflight(
        reporter=reporter,
        media_root=media_root,
        provider_status=provider_status,
        analysis_config=analysis_config,
    )

    def status_callback(message: str) -> None:
        route_status_message(reporter=reporter, message=message, start_time=start_time)

    def progress_callback(processed: int, total: int, asset: Asset) -> None:
        reporter.progress(
            processed=processed,
            total=total,
            asset_name=asset.name,
            start_time=start_time,
            activity="Analyzing",
        )

    previous_stderr = sys.stderr
    sys.stderr = stderr_proxy
    try:
        try:
            project = scan_and_analyze_media_root(
                project_name=project_name,
                media_roots=[media_root],
                story_prompt=story_prompt,
                artifacts_root=artifacts_root,
                status_callback=status_callback,
                progress_callback=progress_callback,
            )
        except KeyboardInterrupt:
            reporter.finish()
            reporter.error("Process", "Interrupted from keyboard.")
            return 130
    finally:
        sys.stderr = previous_stderr
    reporter.finish()
    if not project.assets:
        reporter.warn("Process", "No source assets were available to process.")
    sys.stdout.write(__import__("json").dumps(project.to_dict(), indent=2))
    return 0


def emit_preflight(*, reporter: ProcessReporter, media_root: str, provider_status, analysis_config) -> None:
    reporter.header("Process Preflight")
    reporter.info("Input", f"Media root: {media_root}")
    reporter.info(
        "AI Runtime",
        "Configured provider: "
        f"{provider_status.configured_provider or 'deterministic'}"
        + (f" ({provider_status.model})" if provider_status.model else ""),
    )
    if provider_status.revision:
        reporter.info("AI Runtime", f"Model revision: {provider_status.revision}")
    if provider_status.cache_dir:
        reporter.info("AI Runtime", f"Model cache: {provider_status.cache_dir}")
    if provider_status.device:
        reporter.info("AI Runtime", f"Requested device: {provider_status.device}")
    reporter.info(
        "AI Runtime",
        "Execution mode: "
        f"{analysis_config.mode} | "
        f"shortlist {analysis_config.max_segments_per_asset}/asset | "
        f"keyframes {analysis_config.max_keyframes_per_segment} | "
        f"width {analysis_config.keyframe_max_width}px | "
        f"concurrency {analysis_config.concurrency} | "
        f"cache {'on' if analysis_config.cache_enabled else 'off'}",
    )
    provider_message = provider_status.detail.strip()
    if provider_message:
        provider_section = "AI Runtime"
        if provider_status.available:
            reporter.success(provider_section, provider_message)
        elif provider_status.configured_provider != "deterministic":
            reporter.warn(provider_section, provider_message)
            reporter.warn(
                provider_section,
                f"Effective provider: {provider_status.effective_provider} (fallback active)",
            )
        else:
            reporter.info(provider_section, provider_message)
    reporter.info(
        "Transcript",
        f"Configured provider: {analysis_config.transcript_provider} | model size: {analysis_config.transcript_model_size}",
    )


def route_status_message(*, reporter: ProcessReporter, message: str, start_time: float) -> None:
    stripped = message.strip()
    if not stripped:
        return

    analyze_match = ANALYZE_RE.match(stripped)
    if analyze_match:
        if reporter.interactive:
            reporter.progress(
                processed=max(0, int(analyze_match.group("index")) - 1),
                total=int(analyze_match.group("total")),
                asset_name=analyze_match.group("asset"),
                start_time=start_time,
                activity="Analyzing",
            )
        return

    low_signal_prefixes = (
        "✓ Sampled",
        "✓ Speech gate:",
        "✓ Speech probe:",
        "✓ Deduplicating",
        "✓ CLIP semantic scoring",
        "✓ VLM targets:",
        "→ Eliminated",
        "→ Gated",
        "════════",
        "Analysis Complete - Summary",
        "Assets processed:",
        "Total candidate segments:",
        "Frames sampled:",
        "Deduplication:",
        "Prefilter shortlisted:",
        "CLIP semantic scoring:",
        "Audio coverage:",
        "Transcript coverage:",
        "VLM analysis:",
        "Deterministic analysis:",
        "Story assembly:",
        "AI results:",
        "Runtime reliability:",
        "Runtime degraded modes:",
        "Runtime intentional skips:",
    )
    if any(stripped.startswith(prefix) for prefix in low_signal_prefixes):
        return

    if stripped.startswith("Discovered ") or stripped.startswith("Matched "):
        reporter.info("Discovery", stripped)
        return

    if stripped.startswith("Transcript support:") or "faster-whisper" in stripped.lower():
        severity = "warn" if "unavailable" in stripped.lower() else "info"
        if severity == "warn":
            reporter.warn("Transcript", stripped)
        else:
            reporter.info("Transcript", stripped)
        return

    if "⚠" in stripped or "unavailable" in stripped.lower():
        reporter.warn("Process", stripped.replace("⚠", "").strip())
        return

    reporter.info("Process", stripped)


if __name__ == "__main__":
    raise SystemExit(main())
