from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from os.path import basename
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
    "semantic_boundary_eligible_count",
    "semantic_boundary_request_count",
    "semantic_boundary_validated_count",
    "semantic_boundary_skipped_count",
    "semantic_boundary_fallback_count",
    "semantic_boundary_threshold_targeted_count",
    "semantic_boundary_floor_targeted_count",
    "semantic_boundary_applied_count",
    "semantic_boundary_noop_count",
    "deterministic_preprocessing_cache_hit_asset_count",
    "deterministic_preprocessing_cache_rebuilt_asset_count",
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
    runtime_stability: dict[str, Any]
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


def classify_ai_cache_activity(*, workload_counts: dict[str, Any]) -> str:
    live_segments = int(workload_counts.get("ai_live_segment_count", 0) or 0)
    cached_segments = int(workload_counts.get("ai_cached_segment_count", 0) or 0)
    if live_segments > 0 and cached_segments > 0:
        return "mixed-cache"
    if cached_segments > 0:
        return "warm-cache"
    if live_segments > 0:
        return "cold-cache"
    return "inactive"


def classify_preprocessing_cache_activity(*, workload_counts: dict[str, Any]) -> str:
    hit_assets = int(workload_counts.get("deterministic_preprocessing_cache_hit_asset_count", 0) or 0)
    rebuilt_assets = int(workload_counts.get("deterministic_preprocessing_cache_rebuilt_asset_count", 0) or 0)
    if hit_assets > 0 and rebuilt_assets > 0:
        return "mixed-preprocessing"
    if hit_assets > 0:
        return "warm-preprocessing"
    if rebuilt_assets > 0:
        return "cold-preprocessing"
    return "inactive"


def derive_ai_execution_context(
    *,
    provider_effective: str,
    configured_concurrency: int,
) -> dict[str, Any]:
    configured = max(1, int(configured_concurrency))
    if provider_effective == "mlx-vlm-local":
        return {
            "ai_concurrency": configured,
            "ai_effective_concurrency": 1,
            "ai_execution_context": "serialized-local-model",
        }
    if provider_effective == "lmstudio":
        return {
            "ai_concurrency": configured,
            "ai_effective_concurrency": configured,
            "ai_execution_context": "configured-parallel-requests",
        }
    return {
        "ai_concurrency": configured,
        "ai_effective_concurrency": 0,
        "ai_execution_context": "deterministic-fallback",
    }


def build_runtime_stability_context(
    *,
    project_payload: dict[str, Any],
    runtime_configuration: dict[str, Any],
) -> dict[str, Any]:
    analysis_summary = dict((project_payload.get("project") or {}).get("analysis_summary") or {})
    degraded_reasons = [str(item) for item in analysis_summary.get("runtime_degraded_reasons", []) or [] if str(item)]
    intentional_skip_reasons = [
        str(item) for item in analysis_summary.get("runtime_intentional_skip_reasons", []) or [] if str(item)
    ]
    component_modes = {
        "ai": str(analysis_summary.get("ai_runtime_mode", "inactive")),
        "transcript": str(analysis_summary.get("transcript_runtime_mode", "inactive")),
        "semantic_boundary": str(analysis_summary.get("semantic_boundary_runtime_mode", "inactive")),
        "cache": str(analysis_summary.get("cache_runtime_mode", "inactive")),
    }
    return {
        "overall_mode": str(analysis_summary.get("runtime_reliability_mode", "inactive")),
        "ready": bool(analysis_summary.get("runtime_ready", False)),
        "summary": str(analysis_summary.get("runtime_reliability_summary", "")),
        "component_modes": component_modes,
        "degraded_reasons": degraded_reasons,
        "intentional_skip_reasons": intentional_skip_reasons,
        "semantic_targeting_mode": str(analysis_summary.get("semantic_boundary_targeting_mode", "inactive")),
        "transcript_status": str(analysis_summary.get("transcript_status", "")),
        "transcript_provider_effective": str(
            analysis_summary.get(
                "transcript_provider_effective",
                runtime_configuration.get("transcript_provider_configured", ""),
            )
        ),
        "ai_provider_effective": str(runtime_configuration.get("ai_provider_effective", "")),
        "ai_execution_context": str(runtime_configuration.get("ai_execution_context", "")),
        "ai_effective_concurrency": int(runtime_configuration.get("ai_effective_concurrency", 0) or 0),
        "ai_cache_activity": classify_ai_cache_activity(workload_counts=analysis_summary),
        "deterministic_preprocessing_cache_activity": classify_preprocessing_cache_activity(
            workload_counts=analysis_summary
        ),
    }


def attach_quality_evaluation(
    *,
    benchmark_root: str | Path,
    run_id: str,
    evaluation_result: dict[str, Any],
    summary_path: str | Path | None = None,
) -> Path:
    root = Path(benchmark_root)
    run_dir = root / run_id
    benchmark_path = run_dir / "benchmark.json"
    evaluation_path = run_dir / "segmentation-evaluation.json"

    benchmark_payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    evaluation_path.write_text(
        json.dumps(evaluation_result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    benchmark_payload["quality_evaluation"] = evaluation_result
    artifact_paths = dict(benchmark_payload.get("artifact_paths", {}))
    artifact_paths["segmentation_evaluation_json"] = str(evaluation_path)
    if summary_path is not None:
        artifact_paths["segmentation_evaluation_summary"] = str(Path(summary_path))
    benchmark_payload["artifact_paths"] = artifact_paths
    benchmark_path.write_text(
        json.dumps(benchmark_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    history_path = root / "history.jsonl"
    if history_path.exists():
        entries = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for entry in entries:
            if entry.get("run_id") == run_id:
                timeline_results = dict(evaluation_result.get("timeline_results") or {})
                timeline_summary = {
                    "passed": bool(timeline_results.get("passed", False)),
                    "failed_check_count": sum(
                        1
                        for check in timeline_results.get("checks", [])
                        if not bool(check.get("passed", False))
                    ),
                    "observed": dict(timeline_results.get("observed") or {}),
                }
                entry["quality_evaluation_summary"] = {
                    "fixture_set": evaluation_result.get("fixture_set", ""),
                    "passed": bool(evaluation_result.get("passed", False)),
                    "failed_check_count": int((evaluation_result.get("summary") or {}).get("failed_check_count", 0)),
                    "semantic_validation": dict(evaluation_result.get("semantic_validation") or {}),
                    "timeline": timeline_summary,
                }
        history_path.write_text(
            "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
            encoding="utf-8",
        )
    return evaluation_path


def derive_dataset_identity(
    *,
    project_payload: dict[str, Any],
    media_dir: str = "",
    media_dir_input: str = "",
) -> dict[str, Any]:
    assets = project_payload.get("assets", []) or []
    asset_tokens: list[str] = []
    for asset in assets:
        token = (
            str(asset.get("interchange_reel_name") or "").strip()
            or str(asset.get("name") or "").strip()
            or basename(str(asset.get("source_path") or "").strip())
            or str(asset.get("id") or "").strip()
        )
        if token:
            asset_tokens.append(token)
    asset_tokens = sorted(set(asset_tokens))
    payload = {
        "asset_tokens": asset_tokens,
        "asset_count": len(assets),
    }
    fingerprint = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:12]
    label_source = media_dir_input or media_dir
    label = basename(str(label_source).rstrip("/")) if label_source else ""
    if not label:
        label = asset_tokens[0] if asset_tokens else "unknown-dataset"
    return {
        "fingerprint": fingerprint,
        "label": label,
        "asset_count": len(assets),
        "asset_tokens": asset_tokens,
    }


def load_runtime_configuration(*, media_dir: str, media_dir_input: str) -> dict[str, Any]:
    provider_status = inspect_ai_provider_status(runtime_probe=True)
    analysis_config = load_ai_analysis_config()
    ai_execution_context = derive_ai_execution_context(
        provider_effective=provider_status.effective_provider,
        configured_concurrency=analysis_config.concurrency,
    )
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
        **ai_execution_context,
        "ai_cache_enabled": analysis_config.cache_enabled,
        "transcript_provider_configured": analysis_config.transcript_provider,
        "transcript_model_size": analysis_config.transcript_model_size,
        "clip_enabled": analysis_config.clip_enabled,
        "clip_available": is_clip_available(),
        "clip_min_score": analysis_config.clip_min_score if analysis_config.clip_enabled else None,
        "clip_model": analysis_config.clip_model if analysis_config.clip_enabled else None,
        "vlm_budget_pct": analysis_config.vlm_budget_pct,
        "semantic_boundary_validation_enabled": analysis_config.semantic_boundary_validation_enabled,
        "semantic_boundary_ambiguity_threshold": analysis_config.semantic_boundary_ambiguity_threshold,
        "semantic_boundary_floor_threshold": analysis_config.semantic_boundary_floor_threshold,
        "semantic_boundary_min_targets": analysis_config.semantic_boundary_min_targets,
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
    dataset_identity = derive_dataset_identity(
        project_payload=project_payload,
        media_dir=str(runtime_configuration.get("media_dir") or ""),
        media_dir_input=str(runtime_configuration.get("media_dir_input") or ""),
    )
    for key in WORKLOAD_COUNT_KEYS:
        if key == "asset_count":
            continue
        if key in analysis_summary:
            workload_counts[key] = analysis_summary[key]
    runtime_stability = build_runtime_stability_context(
        project_payload=project_payload,
        runtime_configuration=runtime_configuration,
    )

    return ProcessBenchmark(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        total_runtime_sec=round(float(total_runtime_sec), 3),
        phase_timings_sec=phase_timings,
        workload_counts=workload_counts,
        runtime_configuration={**runtime_configuration, "dataset_identity": dataset_identity},
        runtime_stability=runtime_stability,
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


def load_previous_matching_benchmark_entry(
    history_path: str | Path,
    *,
    dataset_fingerprint: str,
    exclude_run_id: str | None = None,
) -> dict[str, Any] | None:
    path = Path(history_path)
    if not path.exists():
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in reversed(lines):
        entry = json.loads(line)
        if exclude_run_id and entry.get("run_id") == exclude_run_id:
            continue
        dataset = dict(entry.get("dataset_identity") or {})
        if dataset.get("fingerprint") == dataset_fingerprint:
            return entry
    return None


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
    baseline_runtime_stability = dict(baseline_entry.get("runtime_stability") or {})
    current_workload = current.workload_counts
    baseline_workload = baseline_entry.get("workload_counts", {})
    current_dataset = dict(current_cfg.get("dataset_identity") or {})
    baseline_dataset = dict(baseline_entry.get("dataset_identity") or {})

    differences: list[str] = []
    if current_dataset.get("fingerprint") != baseline_dataset.get("fingerprint"):
        differences.append(
            "dataset changed "
            f"({baseline_dataset.get('label', 'unknown')} -> {current_dataset.get('label', 'unknown')})"
        )
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
    if current_cfg.get("ai_effective_concurrency") != baseline_cfg.get("ai_effective_concurrency"):
        differences.append(
            "effective AI concurrency changed "
            f"({baseline_cfg.get('ai_effective_concurrency', 'unknown')} -> {current_cfg.get('ai_effective_concurrency', 'unknown')})"
        )
    if current_cfg.get("ai_execution_context") != baseline_cfg.get("ai_execution_context"):
        differences.append(
            "AI execution context changed "
            f"({baseline_cfg.get('ai_execution_context', 'unknown')} -> {current_cfg.get('ai_execution_context', 'unknown')})"
        )
    if current_cfg.get("semantic_boundary_ambiguity_threshold") != baseline_cfg.get("semantic_boundary_ambiguity_threshold"):
        differences.append(
            "semantic ambiguity threshold changed "
            f"({baseline_cfg.get('semantic_boundary_ambiguity_threshold', 'unknown')} -> {current_cfg.get('semantic_boundary_ambiguity_threshold', 'unknown')})"
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
    if current_workload.get("semantic_boundary_request_count") != baseline_workload.get("semantic_boundary_request_count"):
        differences.append(
            "semantic boundary request volume changed "
            f"({baseline_workload.get('semantic_boundary_request_count', 0)} -> "
            f"{current_workload.get('semantic_boundary_request_count', 0)})"
        )
    current_ai_cache_activity = classify_ai_cache_activity(workload_counts=current_workload)
    baseline_ai_cache_activity = classify_ai_cache_activity(workload_counts=baseline_workload)
    if current_ai_cache_activity != baseline_ai_cache_activity:
        differences.append(
            f"AI cache activity changed ({baseline_ai_cache_activity} -> {current_ai_cache_activity})"
        )
    current_preprocessing_cache_activity = classify_preprocessing_cache_activity(workload_counts=current_workload)
    baseline_preprocessing_cache_activity = classify_preprocessing_cache_activity(workload_counts=baseline_workload)
    if current_preprocessing_cache_activity != baseline_preprocessing_cache_activity:
        differences.append(
            "deterministic preprocessing cache activity changed "
            f"({baseline_preprocessing_cache_activity} -> {current_preprocessing_cache_activity})"
        )
    current_runtime_stability = dict(current.runtime_stability or {})
    if current_runtime_stability.get("overall_mode") != baseline_runtime_stability.get("overall_mode"):
        differences.append(
            "runtime reliability mode changed "
            f"({baseline_runtime_stability.get('overall_mode', 'unknown')} -> "
            f"{current_runtime_stability.get('overall_mode', 'unknown')})"
        )
    current_component_modes = dict(current_runtime_stability.get("component_modes") or {})
    baseline_component_modes = dict(baseline_runtime_stability.get("component_modes") or {})
    for key, label in (
        ("ai", "AI runtime"),
        ("transcript", "transcript runtime"),
        ("semantic_boundary", "semantic boundary runtime"),
        ("cache", "cache runtime"),
    ):
        if current_component_modes.get(key) != baseline_component_modes.get(key):
            differences.append(
                f"{label} changed "
                f"({baseline_component_modes.get(key, 'unknown')} -> {current_component_modes.get(key, 'unknown')})"
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
        "runtime_configuration": dict(benchmark.runtime_configuration),
        "runtime_stability": benchmark.runtime_stability,
        "dataset_identity": dict(benchmark.runtime_configuration.get("dataset_identity") or {}),
        "workload_counts": dict(benchmark.workload_counts),
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
    timeline_items = list((project_payload.get("timeline") or {}).get("items", []) or [])

    lines = [
        "Run Overview:",
        f"Run ID: {benchmark.run_id}",
        (
            "Workload: "
            f"{len(assets)} assets | "
            f"{len(proxy_backed)} proxy-backed | "
            f"{len(source_only)} source-only"
        ),
    ]
    if analysis_summary:
        lines.append(
            "Segments: "
            f"{analysis_summary.get('candidate_segment_count', 0)} candidates | "
            f"{analysis_summary.get('prefilter_shortlisted_count', 0)} shortlisted | "
            f"{analysis_summary.get('vlm_target_count', 0)} VLM targets | "
            f"{analysis_summary.get('filtered_before_vlm_count', 0)} deterministic-only"
        )
        lines.append(
            "Audio: "
            f"{analysis_summary.get('audio_signal_asset_count', 0)} with audio | "
            f"{analysis_summary.get('audio_silent_asset_count', 0)} silent/no-audio"
        )
        if timeline_items:
            lines.append(f"Timeline: {len(timeline_items)} items assembled")

    configured_ai_concurrency = benchmark.runtime_configuration.get("ai_concurrency")
    effective_ai_concurrency = benchmark.runtime_configuration.get("ai_effective_concurrency")
    ai_execution_context = str(benchmark.runtime_configuration.get("ai_execution_context", "")).strip()
    ai_provider = str(benchmark.runtime_configuration.get("ai_provider_effective", "")).strip()
    configured_ai_provider = str(benchmark.runtime_configuration.get("ai_provider_configured", "")).strip()
    ai_cache_activity = classify_ai_cache_activity(workload_counts=benchmark.workload_counts)
    preprocessing_cache_activity = classify_preprocessing_cache_activity(workload_counts=benchmark.workload_counts)

    runtime_stability = dict(benchmark.runtime_stability or {})
    lines.extend(["", "Runtime Path:"])
    if ai_provider:
        lines.append(
            "AI: "
            f"configured {configured_ai_provider or ai_provider} -> effective {ai_provider}"
            + (
                f" | concurrency {configured_ai_concurrency}->{effective_ai_concurrency}"
                if configured_ai_concurrency is not None and effective_ai_concurrency is not None
                else ""
            )
            + (f" | {ai_execution_context}" if ai_execution_context else "")
        )
    lines.append(
        "AI workload: "
        f"{benchmark.workload_counts.get('ai_live_segment_count', 0)} live | "
        f"{benchmark.workload_counts.get('ai_cached_segment_count', 0)} cached | "
        f"{benchmark.workload_counts.get('ai_fallback_segment_count', 0)} fallback | "
        f"cache {ai_cache_activity}"
    )
    lines.append(
        "Preprocessing cache: "
        f"{preprocessing_cache_activity} "
        f"({benchmark.workload_counts.get('deterministic_preprocessing_cache_hit_asset_count', 0)} reused, "
        f"{benchmark.workload_counts.get('deterministic_preprocessing_cache_rebuilt_asset_count', 0)} rebuilt)"
    )

    if analysis_summary:
        lines.append(
            "Transcript: "
            f"{analysis_summary.get('transcript_status', 'unknown')} "
            f"via {analysis_summary.get('transcript_provider_effective', 'none')} | "
            f"{analysis_summary.get('transcript_target_asset_count', 0)} targeted | "
            f"{analysis_summary.get('transcript_cached_asset_count', 0)} cached | "
            f"{analysis_summary.get('transcript_skipped_asset_count', 0)} skipped | "
            f"{analysis_summary.get('transcript_probe_rejected_asset_count', 0)} probe rejections"
        )
        lines.append(
            "Semantic: "
            f"{analysis_summary.get('semantic_boundary_runtime_mode', 'inactive')} | "
            f"{analysis_summary.get('semantic_boundary_request_count', 0)} requests | "
            f"{analysis_summary.get('semantic_boundary_skipped_count', 0)} skipped"
        )
        clip_scored = int(analysis_summary.get("clip_scored_count", 0) or 0)
        clip_gated = int(analysis_summary.get("clip_gated_count", 0) or 0)
        if clip_scored > 0:
            lines.append(f"CLIP: {clip_scored} scored | {clip_gated} gated")
        if analysis_summary.get("story_assembly_active", False):
            lines.append(
                "Story assembly: "
                f"{analysis_summary.get('story_assembly_strategy', 'unknown')} | "
                f"{analysis_summary.get('story_assembly_mode_alternation_count', 0)} alternations | "
                f"{analysis_summary.get('story_assembly_tradeoff_count', 0)} tradeoffs"
            )

    if comparison is None:
        comparison_line = "Comparison: no prior benchmark available"
    else:
        comparison_line = (
            "Comparison: "
            f"vs {comparison.baseline_run_id} "
            f"({format_runtime(comparison.baseline_total_runtime_sec)}) "
            f"{format_runtime_delta(comparison.total_runtime_delta_sec, comparison.total_runtime_delta_pct)}"
        )
    lines.extend(["", "Timing:", f"Total runtime: {format_runtime(benchmark.total_runtime_sec)}"])
    if benchmark.phase_timings_sec:
        lines.append("Phases: " + format_phase_summary(benchmark.phase_timings_sec))
    lines.append(comparison_line)
    if comparison is not None and comparison.context_differences:
        lines.append("Context: " + "; ".join(comparison.context_differences[:3]))

    if runtime_stability:
        lines.extend(["", "Runtime Reliability:"])
        component_modes = dict(runtime_stability.get("component_modes") or {})
        lines.append(
            "Modes: "
            f"overall {runtime_stability.get('overall_mode', 'unknown')} | "
            f"AI {component_modes.get('ai', 'unknown')} | "
            f"transcript {component_modes.get('transcript', 'unknown')} | "
            f"semantic {component_modes.get('semantic_boundary', 'unknown')} | "
            f"cache {component_modes.get('cache', 'unknown')}"
        )
        summary = str(runtime_stability.get("summary", "")).strip()
        if summary:
            lines.append(f"Summary: {summary}")
        degraded_reasons = [str(item) for item in runtime_stability.get("degraded_reasons", []) or [] if str(item)]
        if degraded_reasons:
            lines.append("Degraded: " + "; ".join(degraded_reasons))
        intentional_skip_reasons = [
            str(item) for item in runtime_stability.get("intentional_skip_reasons", []) or [] if str(item)
        ]
        if intentional_skip_reasons:
            lines.append("Intentional skips: " + "; ".join(intentional_skip_reasons))

    lines.extend(
        [
            "",
            "Artifacts:",
            f"Project JSON: {benchmark.artifact_paths.get('project_json', '')}",
            f"Process output: {benchmark.artifact_paths.get('process_output', '')}",
            f"Process summary: {benchmark.artifact_paths.get('process_summary', '')}",
            f"Benchmark JSON: {benchmark.artifact_paths.get('benchmark_json', '')}",
        ]
    )

    if vlm_debug_file and Path(vlm_debug_file).is_file():
        lines.append(f"VLM debug log: {vlm_debug_file}")

    return lines


def format_phase_summary(phase_timings_sec: dict[str, float]) -> str:
    parts: list[str] = []
    for phase_name, label in PHASE_LABELS.items():
        if phase_name in phase_timings_sec:
            parts.append(f"{label} {format_runtime(phase_timings_sec[phase_name])}")
    return " | ".join(parts)


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
