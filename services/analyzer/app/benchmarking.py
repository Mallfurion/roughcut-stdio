from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .ai import inspect_ai_provider_status, load_ai_analysis_config
from .clip import is_available as is_clip_available

PHASE_LABELS = {
    "media_discovery": "Media discovery",
    "per_asset_analysis": "Per-asset analysis",
    "take_selection": "Take selection",
    "timeline_assembly": "Timeline assembly",
}

WORKLOAD_COUNT_KEYS = (
    "asset_count",
    "prefilter_sample_count",
    "candidate_segment_count",
    "deduplicated_segment_count",
    "dedup_group_count",
    "dedup_eliminated_count",
    "prefilter_shortlisted_count",
    "vlm_target_count",
    "filtered_before_vlm_count",
    "audio_signal_asset_count",
    "audio_silent_asset_count",
    "transcript_target_asset_count",
    "transcript_skipped_asset_count",
    "transcript_probed_asset_count",
    "transcript_probe_rejected_asset_count",
    "transcribed_asset_count",
    "transcript_failed_asset_count",
    "transcript_cached_asset_count",
    "transcript_runtime_probed_asset_count",
    "transcript_runtime_probe_rejected_asset_count",
    "transcript_excerpt_segment_count",
    "speech_fallback_segment_count",
    "clip_scored_count",
    "clip_gated_count",
    "ai_live_segment_count",
    "ai_cached_segment_count",
    "ai_fallback_segment_count",
    "ai_live_request_count",
)


@dataclass(slots=True)
class ProcessBenchmark:
    run_id: str
    started_at: str
    completed_at: str
    total_runtime_sec: float
    phase_timings_sec: dict[str, float]
    workload_counts: dict[str, int | float]
    runtime_configuration: dict[str, Any]
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BenchmarkComparison:
    baseline_run_id: str
    baseline_total_runtime_sec: float
    total_runtime_delta_sec: float
    total_runtime_delta_pct: float | None
    context_differences: list[str]


def load_runtime_configuration(*, media_dir: str, media_dir_input: str) -> dict[str, Any]:
    provider_status = inspect_ai_provider_status(runtime_probe=True)
    analysis_config = load_ai_analysis_config()
    return {
        "media_dir": media_dir,
        "media_dir_input": media_dir_input,
        "ai_provider_configured": provider_status.configured_provider,
        "ai_provider_effective": provider_status.effective_provider,
        "ai_model": provider_status.model,
        "ai_revision": provider_status.revision,
        "ai_base_url": provider_status.base_url,
        "ai_cache_dir": provider_status.cache_dir,
        "ai_device": provider_status.device,
        "ai_available": provider_status.available,
        "ai_detail": provider_status.detail,
        "ai_mode": analysis_config.mode,
        "ai_max_segments_per_asset": analysis_config.max_segments_per_asset,
        "ai_max_keyframes_per_segment": analysis_config.max_keyframes_per_segment,
        "ai_keyframe_max_width": analysis_config.keyframe_max_width,
        "ai_concurrency": analysis_config.concurrency,
        "ai_cache_enabled": analysis_config.cache_enabled,
        "transcript_provider_configured": analysis_config.transcript_provider,
        "transcript_model_size": analysis_config.transcript_model_size,
        "clip_enabled": analysis_config.clip_enabled,
        "clip_available": is_clip_available(),
        "clip_min_score": analysis_config.clip_min_score if analysis_config.clip_enabled else None,
        "clip_model": analysis_config.clip_model if analysis_config.clip_enabled else None,
        "vlm_budget_pct": analysis_config.vlm_budget_pct,
    }


def build_process_benchmark(
    *,
    run_id: str,
    started_at: str,
    completed_at: str,
    total_runtime_sec: float,
    project_payload: dict[str, Any],
    runtime_configuration: dict[str, Any],
    artifact_paths: dict[str, str],
) -> ProcessBenchmark:
    analysis_summary = project_payload.get("project", {}).get("analysis_summary", {})
    phase_timings = {
        key: round(float(value), 3)
        for key, value in analysis_summary.get("phase_timings_sec", {}).items()
        if key in PHASE_LABELS
    }
    workload_counts = {
        "asset_count": len(project_payload.get("assets", [])),
    }
    for key in WORKLOAD_COUNT_KEYS:
        if key == "asset_count":
            continue
        if key in analysis_summary:
            workload_counts[key] = analysis_summary[key]

    return ProcessBenchmark(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        total_runtime_sec=round(float(total_runtime_sec), 3),
        phase_timings_sec=phase_timings,
        workload_counts=workload_counts,
        runtime_configuration=runtime_configuration,
        artifact_paths=artifact_paths,
    )


def load_previous_benchmark_entry(history_path: str | Path) -> dict[str, Any] | None:
    path = Path(history_path)
    if not path.exists():
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def compare_benchmarks(
    current: ProcessBenchmark,
    baseline_entry: dict[str, Any] | None,
) -> BenchmarkComparison | None:
    if baseline_entry is None:
        return None

    baseline_runtime = float(baseline_entry.get("total_runtime_sec", 0.0))
    delta_sec = round(current.total_runtime_sec - baseline_runtime, 3)
    delta_pct = None
    if baseline_runtime > 0:
        delta_pct = round((delta_sec / baseline_runtime) * 100.0, 1)

    current_cfg = current.runtime_configuration
    baseline_cfg = baseline_entry.get("runtime_configuration", {})
    current_workload = current.workload_counts
    baseline_workload = baseline_entry.get("workload_counts", {})

    differences: list[str] = []
    if current_cfg.get("media_dir") != baseline_cfg.get("media_dir"):
        differences.append(
            f"media root changed ({baseline_cfg.get('media_dir', 'unknown')} -> {current_cfg.get('media_dir', 'unknown')})"
        )
    if current_cfg.get("ai_provider_effective") != baseline_cfg.get("ai_provider_effective"):
        differences.append(
            "effective AI provider changed "
            f"({baseline_cfg.get('ai_provider_effective', 'unknown')} -> {current_cfg.get('ai_provider_effective', 'unknown')})"
        )
    if current_cfg.get("ai_mode") != baseline_cfg.get("ai_mode"):
        differences.append(
            f"AI mode changed ({baseline_cfg.get('ai_mode', 'unknown')} -> {current_cfg.get('ai_mode', 'unknown')})"
        )
    if current_workload.get("asset_count") != baseline_workload.get("asset_count"):
        differences.append(
            f"asset count changed ({baseline_workload.get('asset_count', 0)} -> {current_workload.get('asset_count', 0)})"
        )
    if current_workload.get("candidate_segment_count") != baseline_workload.get("candidate_segment_count"):
        differences.append(
            "candidate segment count changed "
            f"({baseline_workload.get('candidate_segment_count', 0)} -> {current_workload.get('candidate_segment_count', 0)})"
        )

    return BenchmarkComparison(
        baseline_run_id=str(baseline_entry.get("run_id", "unknown")),
        baseline_total_runtime_sec=baseline_runtime,
        total_runtime_delta_sec=delta_sec,
        total_runtime_delta_pct=delta_pct,
        context_differences=differences,
    )


def write_benchmark_artifacts(
    *,
    benchmark: ProcessBenchmark,
    benchmark_root: str | Path,
) -> Path:
    root = Path(benchmark_root)
    run_dir = root / benchmark.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    benchmark_path = run_dir / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(benchmark.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    history_path = root / "history.jsonl"
    history_entry = {
        "run_id": benchmark.run_id,
        "completed_at": benchmark.completed_at,
        "total_runtime_sec": benchmark.total_runtime_sec,
        "phase_timings_sec": benchmark.phase_timings_sec,
        "runtime_configuration": {
            "media_dir": benchmark.runtime_configuration.get("media_dir"),
            "ai_provider_effective": benchmark.runtime_configuration.get("ai_provider_effective"),
            "ai_mode": benchmark.runtime_configuration.get("ai_mode"),
        },
        "workload_counts": {
            "asset_count": benchmark.workload_counts.get("asset_count", 0),
            "candidate_segment_count": benchmark.workload_counts.get("candidate_segment_count", 0),
            "transcript_target_asset_count": benchmark.workload_counts.get("transcript_target_asset_count", 0),
            "transcript_skipped_asset_count": benchmark.workload_counts.get("transcript_skipped_asset_count", 0),
            "transcript_probed_asset_count": benchmark.workload_counts.get("transcript_probed_asset_count", 0),
            "transcript_probe_rejected_asset_count": benchmark.workload_counts.get("transcript_probe_rejected_asset_count", 0),
            "transcribed_asset_count": benchmark.workload_counts.get("transcribed_asset_count", 0),
            "transcript_cached_asset_count": benchmark.workload_counts.get("transcript_cached_asset_count", 0),
        },
        "benchmark_json": str(benchmark_path),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_entry, sort_keys=True) + "\n")
    return benchmark_path


def write_process_log(
    *,
    path: str | Path,
    benchmark: ProcessBenchmark,
) -> None:
    lines = [
        f"processed_at={benchmark.completed_at}",
        f"run_id={benchmark.run_id}",
        f"project_json={benchmark.artifact_paths.get('project_json', '')}",
        f"media_dir={benchmark.runtime_configuration.get('media_dir', '')}",
        f"media_dir_input={benchmark.runtime_configuration.get('media_dir_input', '')}",
        f"benchmark_json={benchmark.artifact_paths.get('benchmark_json', '')}",
        f"benchmark_history={benchmark.artifact_paths.get('benchmark_history', '')}",
        f"process_output={benchmark.artifact_paths.get('process_output', '')}",
        f"run_process_output={benchmark.artifact_paths.get('run_process_output', '')}",
        f"total_runtime_sec={benchmark.total_runtime_sec:.3f}",
    ]
    for phase_name in PHASE_LABELS:
        if phase_name in benchmark.phase_timings_sec:
            lines.append(f"phase_{phase_name}_sec={benchmark.phase_timings_sec[phase_name]:.3f}")
    for key, value in benchmark.runtime_configuration.items():
        lines.append(f"{key}={_serialize_log_value(value)}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_process_summary(
    *,
    path: str | Path,
    project_payload: dict[str, Any],
    benchmark: ProcessBenchmark,
    comparison: BenchmarkComparison | None,
    vlm_debug_file: str | Path | None = None,
) -> None:
    lines = build_process_summary_lines(
        project_payload=project_payload,
        benchmark=benchmark,
        comparison=comparison,
        vlm_debug_file=vlm_debug_file,
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_process_summary_lines(
    *,
    project_payload: dict[str, Any],
    benchmark: ProcessBenchmark,
    comparison: BenchmarkComparison | None,
    vlm_debug_file: str | Path | None = None,
) -> list[str]:
    assets = project_payload.get("assets", [])
    source_only = [asset for asset in assets if asset.get("has_proxy") is False]
    proxy_backed = [asset for asset in assets if asset.get("has_proxy") is not False]
    analysis_summary = project_payload.get("project", {}).get("analysis_summary", {})

    lines = [
        f"Assets: {len(assets)}",
        f"Proxy-backed assets: {len(proxy_backed)}",
        f"Source-only assets: {len(source_only)}",
        "",
        "Benchmark:",
        f"Run ID: {benchmark.run_id}",
        f"Total runtime: {format_runtime(benchmark.total_runtime_sec)}",
    ]
    if benchmark.phase_timings_sec:
        for phase_name, label in PHASE_LABELS.items():
            if phase_name in benchmark.phase_timings_sec:
                lines.append(f"{label}: {format_runtime(benchmark.phase_timings_sec[phase_name])}")

    if comparison is None:
        lines.append("Benchmark comparison: no prior benchmark available")
    else:
        lines.append(
            "Benchmark comparison: "
            f"vs {comparison.baseline_run_id} "
            f"({format_runtime(comparison.baseline_total_runtime_sec)}) "
            f"{format_runtime_delta(comparison.total_runtime_delta_sec, comparison.total_runtime_delta_pct)}"
        )
        for difference in comparison.context_differences:
            lines.append(f"Comparison context: {difference}")

    if analysis_summary:
        lines.extend(
            [
                "",
                f"Prefilter sampled frames: {analysis_summary.get('prefilter_sample_count', 0)}",
                f"Candidate segments: {analysis_summary.get('candidate_segment_count', 0)}",
                f"Prefilter shortlisted: {analysis_summary.get('prefilter_shortlisted_count', 0)}",
            ]
        )

        clip_scored = analysis_summary.get("clip_scored_count", 0)
        clip_gated = analysis_summary.get("clip_gated_count", 0)
        if clip_scored > 0:
            lines.append(f"CLIP scored segments: {clip_scored}")
            lines.append(f"CLIP gated segments: {clip_gated}")

        clip_dedup_groups = analysis_summary.get("clip_dedup_group_count", 0)
        clip_dedup_elim = analysis_summary.get("clip_dedup_eliminated_count", 0)
        hist_dedup_groups = analysis_summary.get("histogram_dedup_group_count", 0)
        hist_dedup_elim = analysis_summary.get("histogram_dedup_eliminated_count", 0)
        generic_dedup_groups = analysis_summary.get("dedup_group_count", 0)
        generic_dedup_elim = analysis_summary.get("dedup_eliminated_count", 0)

        if clip_dedup_groups > 0:
            lines.append(f"CLIP deduplication: {clip_dedup_elim} eliminated from {clip_dedup_groups} groups")
        if hist_dedup_groups > 0:
            lines.append(f"Histogram deduplication: {hist_dedup_elim} eliminated from {hist_dedup_groups} groups")
        if clip_dedup_groups == 0 and hist_dedup_groups == 0:
            lines.append(f"Deduplication: {generic_dedup_elim} eliminated from {generic_dedup_groups} groups")

        lines.append(f"VLM target segments: {analysis_summary.get('vlm_target_count', 0)}")
        vlm_budget_cap_pct = analysis_summary.get("vlm_budget_cap_pct", 100)
        if vlm_budget_cap_pct < 100:
            vlm_was_binding = analysis_summary.get("vlm_budget_was_binding", False)
            vlm_target_pct = analysis_summary.get("vlm_target_pct_of_candidates", 0.0)
            lines.append(f"VLM budget cap: {vlm_budget_cap_pct}% of candidates")
            if vlm_was_binding:
                lines.append(f"VLM budget was binding ({vlm_target_pct:.1f}% of all candidates selected)")

        lines.append(f"Filtered before VLM: {analysis_summary.get('filtered_before_vlm_count', 0)}")
        lines.append(f"Audio signal assets: {analysis_summary.get('audio_signal_asset_count', 0)}")
        lines.append(f"Silent/no-audio assets: {analysis_summary.get('audio_silent_asset_count', 0)}")
        lines.append(
            "Transcript runtime: "
            f"{analysis_summary.get('transcript_status', 'unknown')} "
            f"({analysis_summary.get('transcript_provider_effective', 'none')})"
        )
        lines.append(f"Transcript-target assets: {analysis_summary.get('transcript_target_asset_count', 0)}")
        lines.append(f"Transcript-skipped assets: {analysis_summary.get('transcript_skipped_asset_count', 0)}")
        lines.append(f"Transcript-probed assets: {analysis_summary.get('transcript_probed_asset_count', 0)}")
        lines.append(f"Transcript probe rejections: {analysis_summary.get('transcript_probe_rejected_asset_count', 0)}")
        lines.append(f"Transcribed assets: {analysis_summary.get('transcribed_asset_count', 0)}")
        lines.append(f"Transcript failures: {analysis_summary.get('transcript_failed_asset_count', 0)}")
        lines.append(f"Transcript cache hits: {analysis_summary.get('transcript_cached_asset_count', 0)}")
        lines.append(f"Transcript excerpt segments: {analysis_summary.get('transcript_excerpt_segment_count', 0)}")
        lines.append(f"Speech fallback segments: {analysis_summary.get('speech_fallback_segment_count', 0)}")
        lines.append(f"AI live segments: {analysis_summary.get('ai_live_segment_count', 0)}")
        lines.append(f"AI cached segments: {analysis_summary.get('ai_cached_segment_count', 0)}")
        lines.append(f"AI fallback segments: {analysis_summary.get('ai_fallback_segment_count', 0)}")
        lines.append(f"AI live requests: {analysis_summary.get('ai_live_request_count', 0)}")

    if source_only:
        lines.extend(["", "Source-only clips:"])
        for asset in source_only[:50]:
            lines.append(f"- {asset['interchange_reel_name']} -> {asset['source_path']}")
            reason = asset.get("proxy_match_reason")
            if reason:
                lines.append(f"  reason: {reason}")

    if vlm_debug_file and Path(vlm_debug_file).is_file():
        lines.extend(["", f"VLM debug log: {vlm_debug_file}"])

    return lines


def format_runtime(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_seconds = int(seconds)
    minutes, remainder = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        clock = f"{hours:02d}:{minutes:02d}:{remainder:02d}"
    else:
        clock = f"{minutes:02d}:{remainder:02d}"
    return f"{clock} ({seconds:.2f}s)"


def format_runtime_delta(delta_sec: float, delta_pct: float | None) -> str:
    direction = "slower" if delta_sec > 0 else "faster" if delta_sec < 0 else "unchanged"
    abs_delta = abs(delta_sec)
    if delta_pct is None:
        return f"{abs_delta:.2f}s {direction}"
    return f"{abs_delta:.2f}s ({abs(delta_pct):.1f}%) {direction}"


def _serialize_log_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)
