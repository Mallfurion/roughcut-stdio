#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.benchmarking import (  # noqa: E402
    build_process_benchmark,
    compare_benchmarks,
    load_previous_matching_benchmark_entry,
    load_runtime_configuration,
    write_benchmark_artifacts,
    write_process_log,
    write_process_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-json", required=True)
    parser.add_argument("--process-log", required=True)
    parser.add_argument("--process-summary", required=True)
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--process-output", required=True)
    parser.add_argument("--run-process-output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    parser.add_argument("--total-runtime-sec", required=True, type=float)
    parser.add_argument("--media-dir", required=True)
    parser.add_argument("--media-dir-input", required=True)
    parser.add_argument("--vlm-debug-file", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_json_path = Path(args.project_json)
    project_payload = json.loads(project_json_path.read_text(encoding="utf-8"))

    benchmark_root = Path(args.benchmark_root)
    benchmark_path = benchmark_root / args.run_id / "benchmark.json"
    history_path = benchmark_root / "history.jsonl"
    runtime_configuration = load_runtime_configuration(
        media_dir=args.media_dir,
        media_dir_input=args.media_dir_input,
    )
    benchmark = build_process_benchmark(
        run_id=args.run_id,
        started_at=args.started_at,
        completed_at=args.completed_at,
        total_runtime_sec=args.total_runtime_sec,
        project_payload=project_payload,
        runtime_configuration=runtime_configuration,
        artifact_paths={
            "project_json": str(project_json_path),
            "process_log": args.process_log,
            "process_summary": args.process_summary,
            "process_output": args.process_output,
            "benchmark_json": str(benchmark_path),
            "benchmark_history": str(history_path),
            "run_process_output": args.run_process_output,
        },
    )
    dataset_identity = dict(benchmark.runtime_configuration.get("dataset_identity") or {})
    comparison = compare_benchmarks(
        benchmark,
        load_previous_matching_benchmark_entry(
            history_path,
            dataset_fingerprint=str(dataset_identity.get("fingerprint", "")),
            exclude_run_id=benchmark.run_id,
        ),
    )
    write_benchmark_artifacts(benchmark=benchmark, benchmark_root=benchmark_root)
    write_process_log(path=args.process_log, benchmark=benchmark)
    write_process_summary(
        path=args.process_summary,
        project_payload=project_payload,
        benchmark=benchmark,
        comparison=comparison,
        vlm_debug_file=args.vlm_debug_file or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
