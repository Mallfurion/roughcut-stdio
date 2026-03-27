from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.analyzer.app.segmentation_evaluation import (
    evaluate_project_for_fixture_set,
    find_fixture_set,
    find_previous_quality_evaluation_for_dataset,
    load_fixture_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "fixtures" / "segmentation-evaluation.json"


class SegmentationEvaluationTests(unittest.TestCase):
    def test_manifest_contains_expected_fixture_set(self) -> None:
        manifest = load_fixture_manifest(MANIFEST_PATH)
        fixture_set = find_fixture_set(manifest, "sample_project_baseline")
        self.assertEqual(fixture_set["name"], "sample_project_baseline")
        self.assertGreaterEqual(len(fixture_set.get("asset_expectations", [])), 3)
        self.assertIn("timeline_expectations", fixture_set)

    def test_evaluate_project_for_fixture_set_reports_pass_and_fail(self) -> None:
        manifest = load_fixture_manifest(MANIFEST_PATH)
        fixture_set = find_fixture_set(manifest, "sample_project_baseline")
        payload = {
            "project": {"analysis_summary": {}},
            "assets": [
                {"id": "asset-city-opening", "name": "City Opening Wide"},
                {"id": "asset-market-dialogue", "name": "Market Dialogue"},
                {"id": "asset-evening-walk", "name": "Evening Walk Detail"},
            ],
            "candidate_segments": [
                {
                    "asset_id": "asset-city-opening",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {},
                },
                {
                    "asset_id": "asset-market-dialogue",
                    "analysis_mode": "speech",
                    "transcript_excerpt": "This is where the day actually starts.",
                    "review_state": {},
                },
                {
                    "asset_id": "asset-evening-walk",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {},
                },
            ],
            "timeline": {
                "story_summary": "Start with city scale, move into the market line, then land on a quieter evening detail.",
                "items": [
                    {
                        "source_reel": "A001_C001_0324AB",
                        "sequence_group": "setup",
                        "sequence_role": "opener",
                    },
                    {
                        "source_reel": "A002_C014_0324CD",
                        "sequence_group": "development",
                        "sequence_role": "spoken beat",
                    },
                    {
                        "source_reel": "A003_C007_0324EF",
                        "sequence_group": "release",
                        "sequence_role": "release",
                    },
                ],
            },
        }

        result = evaluate_project_for_fixture_set(
            project_payload=payload,
            fixture_set=fixture_set,
            manifest_path=MANIFEST_PATH,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["summary"]["failed_check_count"], 0)
        self.assertTrue(result["timeline_results"]["passed"])
        self.assertGreater(result["summary"]["timeline_check_count"], 0)

        payload["timeline"]["items"][0]["source_reel"] = "A002_C014_0324CD"
        failed_result = evaluate_project_for_fixture_set(
            project_payload=payload,
            fixture_set=fixture_set,
            manifest_path=MANIFEST_PATH,
        )

        self.assertFalse(failed_result["passed"])
        self.assertGreater(failed_result["summary"]["failed_check_count"], 0)
        self.assertFalse(failed_result["timeline_results"]["passed"])

    def test_previous_quality_lookup_is_scoped_to_same_dataset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.jsonl"
            entries = [
                {
                    "run_id": "run-001",
                    "dataset_identity": {"fingerprint": "aaaa1111bbbb", "label": "dataset-a"},
                    "quality_evaluation_summary": {
                        "fixture_set": "sample_project_baseline",
                        "passed": True,
                        "failed_check_count": 0,
                    },
                },
                {
                    "run_id": "run-002",
                    "dataset_identity": {"fingerprint": "cccc2222dddd", "label": "dataset-b"},
                    "quality_evaluation_summary": {
                        "fixture_set": "sample_project_baseline",
                        "passed": False,
                        "failed_check_count": 2,
                    },
                },
            ]
            history_path.write_text(
                "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
                encoding="utf-8",
            )

            matched = find_previous_quality_evaluation_for_dataset(
                history_path,
                fixture_set="sample_project_baseline",
                dataset_fingerprint="aaaa1111bbbb",
            )
            self.assertIsNotNone(matched)
            self.assertEqual(matched["run_id"], "run-001")

            unmatched = find_previous_quality_evaluation_for_dataset(
                history_path,
                fixture_set="sample_project_baseline",
                dataset_fingerprint="eeee3333ffff",
            )
            self.assertIsNone(unmatched)


if __name__ == "__main__":
    unittest.main()
