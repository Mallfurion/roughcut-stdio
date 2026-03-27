#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.benchmarking import attach_quality_evaluation  # noqa: E402
from services.analyzer.app.benchmarking import derive_dataset_identity  # noqa: E402
from services.analyzer.app.segmentation_evaluation import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    evaluate_project_for_fixture_set,
    find_fixture_set,
    find_previous_quality_evaluation_for_dataset,
    load_fixture_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-set", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--media-dir", default="")
    parser.add_argument("--skip-process", action="store_true")
    parser.add_argument("--project-json", default="generated/project.json")
    parser.add_argument("--benchmark-root", default="generated/benchmarks")
    parser.add_argument("--summary-path", default="generated/segmentation-evaluation-summary.txt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_fixture_manifest(args.manifest)
    fixture_set = find_fixture_set(manifest, args.fixture_set)

    env = os.environ.copy()
    if args.media_dir:
        env["TIMELINE_MEDIA_DIR"] = args.media_dir

    if not args.skip_process:
        subprocess.run(
            ["npm", "run", "process"],
            cwd=ROOT,
            env=env,
            check=True,
        )

    project_path = ROOT / args.project_json
    project_payload = json.loads(project_path.read_text(encoding="utf-8"))
    dataset_identity = derive_dataset_identity(
        project_payload=project_payload,
        media_dir=env.get("TIMELINE_MEDIA_DIR", ""),
        media_dir_input=args.media_dir,
    )
    evaluation_result = evaluate_project_for_fixture_set(
        project_payload=project_payload,
        fixture_set=fixture_set,
        manifest_path=ROOT / args.manifest,
    )

    history_path = ROOT / args.benchmark_root / "history.jsonl"
    run_id = "no-benchmark-run"
    previous_entry = None
    benchmark_attached = False
    if history_path.exists():
        latest_entry = json.loads([line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()][-1])
        latest_dataset = dict(latest_entry.get("dataset_identity") or {})
        if latest_dataset.get("fingerprint") == dataset_identity.get("fingerprint"):
            run_id = str(latest_entry["run_id"])
        previous_entry = find_previous_quality_evaluation_for_dataset(
            history_path,
            fixture_set=args.fixture_set,
            dataset_fingerprint=str(dataset_identity.get("fingerprint", "")),
            exclude_run_id=run_id if run_id != "no-benchmark-run" else None,
        )

    summary_path = ROOT / args.summary_path
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists() and run_id != "no-benchmark-run":
        attach_quality_evaluation(
            benchmark_root=ROOT / args.benchmark_root,
            run_id=run_id,
            evaluation_result=evaluation_result,
            summary_path=summary_path,
        )
        benchmark_attached = True
    summary_lines = build_summary_lines(
        evaluation_result=evaluation_result,
        previous_entry=previous_entry,
        run_id=run_id,
        benchmark_attach_status=(
            "attached"
            if benchmark_attached
            else "no matching benchmark run for this dataset"
        ),
        dataset_identity=dataset_identity,
    )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("\n".join(summary_lines))
    return 0 if evaluation_result.get("passed", False) else 1


def build_summary_lines(
    *,
    evaluation_result: dict[str, object],
    previous_entry: dict[str, object] | None,
    run_id: str,
    benchmark_attach_status: str,
    dataset_identity: dict[str, object],
) -> list[str]:
    summary = dict(evaluation_result.get("summary") or {})
    lines = [
        "Segmentation Evaluation",
        f"Run ID: {run_id}",
        f"Fixture set: {evaluation_result.get('fixture_set', '')}",
        (
            "Dataset: "
            f"{dataset_identity.get('label', 'unknown')} "
            f"({dataset_identity.get('fingerprint', 'unknown')})"
        ),
        f"Evaluated at: {evaluation_result.get('evaluated_at', datetime.now(timezone.utc).isoformat())}",
        f"Passed: {'yes' if evaluation_result.get('passed', False) else 'no'}",
        (
            "Checks: "
            f"{summary.get('passed_check_count', 0)}/{summary.get('check_count', 0)} passed"
        ),
        f"Benchmark attach: {benchmark_attach_status}",
    ]
    semantic_validation = dict(evaluation_result.get("semantic_validation") or {})
    lines.append(
        "Semantic validation: "
        f"{semantic_validation.get('validated_count', 0)} validated, "
        f"{semantic_validation.get('applied_count', 0)} applied, "
        f"{semantic_validation.get('noop_count', 0)} no-op, "
        f"{semantic_validation.get('floor_targeted_count', 0)} floor-targeted"
    )
    timeline_results = dict(evaluation_result.get("timeline_results") or {})
    if timeline_results:
        timeline_failed = sum(
            1
            for check in timeline_results.get("checks", [])
            if not check.get("passed", False)
        )
        observed = dict(timeline_results.get("observed") or {})
        lines.append(
            "Timeline quality: "
            f"{'pass' if timeline_results.get('passed', False) else 'fail'}, "
            f"{timeline_failed} failed checks, "
            f"{observed.get('item_count', 0)} items"
        )
    if previous_entry is None:
        lines.append("Quality delta: no prior evaluation found for this fixture set and dataset")
    else:
        previous_summary = dict(previous_entry.get("quality_evaluation_summary") or {})
        failed_delta = int(summary.get("failed_check_count", 0)) - int(previous_summary.get("failed_check_count", 0))
        if failed_delta == 0:
            lines.append("Quality delta: failed check count unchanged")
        elif failed_delta < 0:
            lines.append(f"Quality delta: {-failed_delta} fewer failed checks than {previous_entry.get('run_id', 'previous run')}")
        else:
            lines.append(f"Quality delta: {failed_delta} more failed checks than {previous_entry.get('run_id', 'previous run')}")

    failed_asset_checks = [
        check
        for asset in evaluation_result.get("asset_results", [])
        for check in asset.get("checks", [])
        if not check.get("passed", False)
    ]
    failed_summary_checks = [
        check
        for check in evaluation_result.get("analysis_summary_checks", [])
        if not check.get("passed", False)
    ]
    if failed_summary_checks or failed_asset_checks:
        lines.append("Failures:")
        for check in failed_summary_checks[:5]:
            lines.append(f"- {check.get('scope')}: {check.get('message')}")
        for check in failed_asset_checks[:10]:
            lines.append(f"- {check.get('scope')}: {check.get('message')}")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
