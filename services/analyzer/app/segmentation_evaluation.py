from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_PATH = Path("fixtures/segmentation-evaluation.json")


@dataclass(slots=True)
class EvaluationCheck:
    scope: str
    name: str
    expected: str
    actual: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "message": self.message,
        }


def load_fixture_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path or DEFAULT_MANIFEST_PATH)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def find_fixture_set(manifest: dict[str, Any], fixture_set_name: str) -> dict[str, Any]:
    for item in manifest.get("fixture_sets", []):
        if item.get("name") == fixture_set_name:
            return item
    available = ", ".join(sorted(str(item.get("name", "")) for item in manifest.get("fixture_sets", [])))
    raise KeyError(f"Unknown fixture set '{fixture_set_name}'. Available: {available or 'none'}")


def evaluate_project_for_fixture_set(
    *,
    project_payload: dict[str, Any],
    fixture_set: dict[str, Any],
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    analysis_summary = project_payload.get("project", {}).get("analysis_summary", {})
    checks: list[EvaluationCheck] = []

    for metric_name, expectation in (fixture_set.get("analysis_summary_expectations") or {}).items():
        actual = analysis_summary.get(metric_name)
        checks.extend(_evaluate_scalar_expectations("analysis_summary", metric_name, actual, expectation))

    assets = project_payload.get("assets", [])
    candidate_segments = project_payload.get("candidate_segments", [])
    asset_results: list[dict[str, Any]] = []
    for asset_expectation in fixture_set.get("asset_expectations", []):
        asset_name = str(asset_expectation.get("name", "")).strip()
        matching_asset = next((asset for asset in assets if asset.get("name") == asset_name), None)
        asset_checks: list[EvaluationCheck] = []
        if matching_asset is None:
            asset_checks.append(
                EvaluationCheck(
                    scope=f"asset:{asset_name}",
                    name="exists",
                    expected="asset present",
                    actual="missing",
                    passed=False,
                    message=f"Expected asset '{asset_name}' was not present in project output.",
                )
            )
            asset_results.append(
                {
                    "asset_name": asset_name,
                    "category": asset_expectation.get("category", ""),
                    "passed": False,
                    "checks": [item.to_dict() for item in asset_checks],
                }
            )
            checks.extend(asset_checks)
            continue

        segments = [
            segment
            for segment in candidate_segments
            if segment.get("asset_id") == matching_asset.get("id")
        ]
        asset_rules = asset_expectation.get("expectations") or {}
        asset_checks.extend(
            _evaluate_scalar_expectations(
                f"asset:{asset_name}",
                "candidate_segments",
                len(segments),
                {
                    key.removeprefix("candidate_segments_"): value
                    for key, value in asset_rules.items()
                    if key.startswith("candidate_segments_")
                },
            )
        )
        excerpt_count = sum(1 for segment in segments if str(segment.get("transcript_excerpt", "")).strip())
        asset_checks.extend(
            _evaluate_scalar_expectations(
                f"asset:{asset_name}",
                "excerpt_segments",
                excerpt_count,
                {
                    key.removeprefix("excerpt_segments_"): value
                    for key, value in asset_rules.items()
                    if key.startswith("excerpt_segments_")
                },
            )
        )

        modes = sorted(set(str(segment.get("analysis_mode", "")).strip() for segment in segments if segment.get("analysis_mode")))
        required_modes = sorted(str(item) for item in asset_rules.get("required_modes", []))
        if required_modes:
            missing_modes = [mode for mode in required_modes if mode not in modes]
            asset_checks.append(
                EvaluationCheck(
                    scope=f"asset:{asset_name}",
                    name="required_modes",
                    expected=", ".join(required_modes),
                    actual=", ".join(modes) if modes else "none",
                    passed=not missing_modes,
                    message=(
                        f"Observed required analysis modes for '{asset_name}'."
                        if not missing_modes
                        else f"Missing expected analysis modes for '{asset_name}': {', '.join(missing_modes)}."
                    ),
                )
            )

        transcript_statuses = sorted(
            {
                str((segment.get("review_state") or {}).get("transcript_status", "")).strip()
                for segment in segments
                if (segment.get("review_state") or {}).get("transcript_status")
            }
        )
        required_statuses = sorted(str(item) for item in asset_rules.get("required_transcript_statuses", []))
        if required_statuses:
            missing_statuses = [status for status in required_statuses if status not in transcript_statuses]
            asset_checks.append(
                EvaluationCheck(
                    scope=f"asset:{asset_name}",
                    name="required_transcript_statuses",
                    expected=", ".join(required_statuses),
                    actual=", ".join(transcript_statuses) if transcript_statuses else "none",
                    passed=not missing_statuses,
                    message=(
                        f"Observed required transcript statuses for '{asset_name}'."
                        if not missing_statuses
                        else f"Missing expected transcript statuses for '{asset_name}': {', '.join(missing_statuses)}."
                    ),
                )
            )

        forbidden_statuses = sorted(str(item) for item in asset_rules.get("forbidden_transcript_statuses", []))
        if forbidden_statuses:
            present_forbidden = [status for status in forbidden_statuses if status in transcript_statuses]
            asset_checks.append(
                EvaluationCheck(
                    scope=f"asset:{asset_name}",
                    name="forbidden_transcript_statuses",
                    expected=f"not any of {', '.join(forbidden_statuses)}",
                    actual=", ".join(transcript_statuses) if transcript_statuses else "none",
                    passed=not present_forbidden,
                    message=(
                        f"No forbidden transcript statuses observed for '{asset_name}'."
                        if not present_forbidden
                        else f"Observed forbidden transcript statuses for '{asset_name}': {', '.join(present_forbidden)}."
                    ),
                )
            )

        asset_passed = all(item.passed for item in asset_checks)
        checks.extend(asset_checks)
        asset_results.append(
            {
                "asset_name": asset_name,
                "asset_id": matching_asset.get("id"),
                "category": asset_expectation.get("category", ""),
                "passed": asset_passed,
                "checks": [item.to_dict() for item in asset_checks],
            }
        )

    timeline_results = _evaluate_timeline_expectations(
        project_payload=project_payload,
        fixture_set=fixture_set,
    )
    checks.extend(timeline_results["checks"])

    passed_count = sum(1 for item in checks if item.passed)
    failed_count = len(checks) - passed_count
    semantic_validation = {
        "dormant": bool(analysis_summary.get("semantic_boundary_dormant", False)),
        "eligible_count": int(analysis_summary.get("semantic_boundary_eligible_count", 0)),
        "validated_count": int(analysis_summary.get("semantic_boundary_validated_count", 0)),
        "applied_count": int(analysis_summary.get("semantic_boundary_applied_count", 0)),
        "noop_count": int(analysis_summary.get("semantic_boundary_noop_count", 0)),
        "threshold_targeted_count": int(analysis_summary.get("semantic_boundary_threshold_targeted_count", 0)),
        "floor_targeted_count": int(analysis_summary.get("semantic_boundary_floor_targeted_count", 0)),
        "skipped_count": int(analysis_summary.get("semantic_boundary_skipped_count", 0)),
        "fallback_count": int(analysis_summary.get("semantic_boundary_fallback_count", 0)),
    }
    return {
        "fixture_set": fixture_set.get("name"),
        "description": fixture_set.get("description", ""),
        "manifest_path": str(Path(manifest_path or DEFAULT_MANIFEST_PATH).resolve()),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "passed": failed_count == 0,
        "summary": {
            "check_count": len(checks),
            "passed_check_count": passed_count,
            "failed_check_count": failed_count,
            "asset_expectation_count": len(fixture_set.get("asset_expectations", [])),
            "timeline_check_count": len(timeline_results["checks"]),
        },
        "semantic_validation": semantic_validation,
        "analysis_summary_checks": [
            item.to_dict() for item in checks if item.scope == "analysis_summary"
        ],
        "asset_results": asset_results,
        "timeline_results": {
            "passed": timeline_results["passed"],
            "checks": [item.to_dict() for item in timeline_results["checks"]],
            "observed": timeline_results["observed"],
        },
    }


def _evaluate_scalar_expectations(
    scope: str,
    metric_name: str,
    actual: Any,
    expectation: dict[str, Any],
) -> list[EvaluationCheck]:
    if not expectation:
        return []
    checks: list[EvaluationCheck] = []
    if "min" in expectation:
        minimum = expectation["min"]
        passed = actual is not None and actual >= minimum
        checks.append(
            EvaluationCheck(
                scope=scope,
                name=f"{metric_name}.min",
                expected=f">= {minimum}",
                actual=str(actual),
                passed=passed,
                message=(
                    f"{metric_name} met minimum threshold."
                    if passed
                    else f"{metric_name} was below the minimum threshold."
                ),
            )
        )
    if "max" in expectation:
        maximum = expectation["max"]
        passed = actual is not None and actual <= maximum
        checks.append(
            EvaluationCheck(
                scope=scope,
                name=f"{metric_name}.max",
                expected=f"<= {maximum}",
                actual=str(actual),
                passed=passed,
                message=(
                    f"{metric_name} stayed within the maximum threshold."
                    if passed
                    else f"{metric_name} exceeded the maximum threshold."
                ),
            )
        )
    if "exact" in expectation:
        exact = expectation["exact"]
        passed = actual == exact
        checks.append(
            EvaluationCheck(
                scope=scope,
                name=f"{metric_name}.exact",
                expected=str(exact),
                actual=str(actual),
                passed=passed,
                message=(
                    f"{metric_name} matched the exact expected value."
                    if passed
                    else f"{metric_name} did not match the exact expected value."
                ),
            )
        )
    return checks


def _evaluate_timeline_expectations(
    *,
    project_payload: dict[str, Any],
    fixture_set: dict[str, Any],
) -> dict[str, Any]:
    timeline = project_payload.get("timeline", {}) or {}
    timeline_items = list(timeline.get("items", []) or [])
    expectations = fixture_set.get("timeline_expectations") or {}
    if not expectations:
        return {
            "passed": True,
            "checks": [],
            "observed": _timeline_observed_state(timeline, timeline_items),
        }

    checks: list[EvaluationCheck] = []
    observed = _timeline_observed_state(timeline, timeline_items)
    checks.extend(
        _evaluate_scalar_expectations(
            "timeline",
            "item_count",
            len(timeline_items),
            expectations.get("item_count") or {},
        )
    )

    for field_name, observed_values in (
        ("required_sequence_roles", observed["sequence_roles"]),
        ("required_sequence_groups", observed["sequence_groups"]),
        ("required_source_reels", observed["source_reels"]),
    ):
        required_values = sorted(str(item) for item in expectations.get(field_name, []))
        if not required_values:
            continue
        missing = [value for value in required_values if value not in observed_values]
        checks.append(
            EvaluationCheck(
                scope="timeline",
                name=field_name,
                expected=", ".join(required_values),
                actual=", ".join(observed_values) if observed_values else "none",
                passed=not missing,
                message=(
                    f"Observed required timeline values for {field_name}."
                    if not missing
                    else f"Missing expected timeline values for {field_name}: {', '.join(missing)}."
                ),
            )
        )

    story_summary = observed["story_summary"]
    story_summary_contains = [str(item) for item in expectations.get("story_summary_contains", [])]
    for snippet in story_summary_contains:
        checks.append(
            EvaluationCheck(
                scope="timeline",
                name="story_summary_contains",
                expected=snippet,
                actual=story_summary or "",
                passed=snippet.lower() in story_summary.lower(),
                message=(
                    f"Story summary contained '{snippet}'."
                    if snippet.lower() in story_summary.lower()
                    else f"Story summary did not contain expected text '{snippet}'."
                ),
            )
        )

    for field_name, actual_value in (
        ("opener_source_reel", observed["opener_source_reel"]),
        ("release_source_reel", observed["release_source_reel"]),
    ):
        expected_values = [str(item) for item in expectations.get(field_name, [])]
        if not expected_values:
            continue
        checks.append(
            EvaluationCheck(
                scope="timeline",
                name=field_name,
                expected=", ".join(expected_values),
                actual=actual_value or "none",
                passed=actual_value in expected_values,
                message=(
                    f"{field_name} matched an allowed source reel."
                    if actual_value in expected_values
                    else f"{field_name} was '{actual_value or 'none'}', expected one of: {', '.join(expected_values)}."
                ),
            )
        )

    return {
        "passed": all(item.passed for item in checks),
        "checks": checks,
        "observed": observed,
    }


def _timeline_observed_state(
    timeline: dict[str, Any],
    timeline_items: list[dict[str, Any]],
) -> dict[str, Any]:
    sequence_roles = sorted(
        {
            str(item.get("sequence_role", "")).strip()
            for item in timeline_items
            if str(item.get("sequence_role", "")).strip()
        }
    )
    sequence_groups = sorted(
        {
            str(item.get("sequence_group", "")).strip()
            for item in timeline_items
            if str(item.get("sequence_group", "")).strip()
        }
    )
    source_reels = sorted(
        {
            str(item.get("source_reel", "")).strip()
            for item in timeline_items
            if str(item.get("source_reel", "")).strip()
        }
    )
    opener_source_reel = ""
    release_source_reel = ""
    if timeline_items:
        opener_source_reel = str(timeline_items[0].get("source_reel", "")).strip()
        release_source_reel = str(timeline_items[-1].get("source_reel", "")).strip()
    return {
        "item_count": len(timeline_items),
        "story_summary": str(timeline.get("story_summary", "")).strip(),
        "sequence_roles": sequence_roles,
        "sequence_groups": sequence_groups,
        "source_reels": source_reels,
        "opener_source_reel": opener_source_reel,
        "release_source_reel": release_source_reel,
    }


def find_previous_quality_evaluation(
    history_path: str | Path,
    *,
    fixture_set: str,
    exclude_run_id: str | None = None,
) -> dict[str, Any] | None:
    return find_previous_quality_evaluation_for_dataset(
        history_path,
        fixture_set=fixture_set,
        dataset_fingerprint="",
        exclude_run_id=exclude_run_id,
    )


def find_previous_quality_evaluation_for_dataset(
    history_path: str | Path,
    *,
    fixture_set: str,
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
        evaluation_summary = entry.get("quality_evaluation_summary") or {}
        entry_dataset = dict(entry.get("dataset_identity") or {})
        same_dataset = (
            not dataset_fingerprint
            or entry_dataset.get("fingerprint") == dataset_fingerprint
        )
        if evaluation_summary.get("fixture_set") == fixture_set and same_dataset:
            return entry
    return None
