from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.analyzer.app.segmentation_evaluation import (
    evaluate_project_for_fixture_set,
    find_fixture_set,
    load_fixture_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "fixtures" / "segmentation-evaluation.json"


class SegmentationEvaluationTests(unittest.TestCase):
    def test_manifest_contains_expected_fixture_set(self) -> None:
        manifest = load_fixture_manifest(MANIFEST_PATH)
        fixture_set = find_fixture_set(manifest, "ccl2025_media_light")
        self.assertEqual(fixture_set["name"], "ccl2025_media_light")
        self.assertGreaterEqual(len(fixture_set.get("asset_expectations", [])), 4)

    def test_evaluate_project_for_fixture_set_reports_pass_and_fail(self) -> None:
        manifest = load_fixture_manifest(MANIFEST_PATH)
        fixture_set = find_fixture_set(manifest, "ccl2025_media_light")
        payload = {
            "project": {
                "analysis_summary": {
                    "candidate_segment_count": 18,
                    "transcript_target_asset_count": 2,
                    "transcript_probed_asset_count": 5,
                    "speech_fallback_segment_count": 2,
                    "semantic_boundary_dormant": False,
                    "semantic_boundary_eligible_count": 1,
                    "semantic_boundary_validated_count": 1,
                    "semantic_boundary_applied_count": 1,
                    "semantic_boundary_noop_count": 0,
                    "semantic_boundary_threshold_targeted_count": 1,
                    "semantic_boundary_floor_targeted_count": 1,
                    "semantic_boundary_skipped_count": 0,
                    "semantic_boundary_fallback_count": 0,
                }
            },
            "assets": [
                {"id": "asset-1", "name": "Img 8660"},
                {"id": "asset-2", "name": "A001 08101522 C002"},
                {"id": "asset-3", "name": "Dji 0721"},
                {"id": "asset-4", "name": "A001 08101523 C004"},
                {"id": "asset-5", "name": "A001 08101522 C001"},
            ],
            "candidate_segments": [
                {
                    "asset_id": "asset-1",
                    "analysis_mode": "speech",
                    "transcript_excerpt": "Speech one.",
                    "review_state": {"transcript_status": "excerpt-available"},
                },
                {
                    "asset_id": "asset-1",
                    "analysis_mode": "speech",
                    "transcript_excerpt": "Speech two.",
                    "review_state": {"transcript_status": "excerpt-available"},
                },
                {
                    "asset_id": "asset-2",
                    "analysis_mode": "speech",
                    "transcript_excerpt": "Interview excerpt.",
                    "review_state": {"transcript_status": "excerpt-available"},
                },
                {
                    "asset_id": "asset-3",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "not-applicable"},
                },
                {
                    "asset_id": "asset-4",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "selective-skip"},
                },
                {
                    "asset_id": "asset-4",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "selective-skip"},
                },
                {
                    "asset_id": "asset-5",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "selective-skip"},
                },
                {
                    "asset_id": "asset-5",
                    "analysis_mode": "speech",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "selective-skip"},
                },
                {
                    "asset_id": "asset-5",
                    "analysis_mode": "visual",
                    "transcript_excerpt": "",
                    "review_state": {"transcript_status": "selective-skip"},
                },
            ],
        }

        result = evaluate_project_for_fixture_set(
            project_payload=payload,
            fixture_set=fixture_set,
            manifest_path=MANIFEST_PATH,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["summary"]["failed_check_count"], 0)
        self.assertEqual(result["semantic_validation"]["validated_count"], 1)

        payload["project"]["analysis_summary"]["transcript_target_asset_count"] = 5
        failed_result = evaluate_project_for_fixture_set(
            project_payload=payload,
            fixture_set=fixture_set,
            manifest_path=MANIFEST_PATH,
        )

        self.assertFalse(failed_result["passed"])
        self.assertGreater(failed_result["summary"]["failed_check_count"], 0)


if __name__ == "__main__":
    unittest.main()
