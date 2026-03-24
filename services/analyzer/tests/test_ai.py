from __future__ import annotations

import unittest

from services.analyzer.app.ai import (
    AIProviderConfig,
    DeterministicVisionLanguageAnalyzer,
    build_segment_evidence,
    inspect_ai_provider_status,
    keyframe_timestamps_for_segment,
    model_matches,
)
from services.analyzer.app.domain import Asset, CandidateSegment


class AIPhaseOneTests(unittest.TestCase):
    def test_keyframe_timestamps_span_segment(self) -> None:
        timestamps = keyframe_timestamps_for_segment(10.0, 18.0)

        self.assertEqual(len(timestamps), 3)
        self.assertGreater(timestamps[0], 10.0)
        self.assertLess(timestamps[-1], 18.0)

    def test_build_segment_evidence_includes_context_and_metrics(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Crowd Wide",
            source_path="/tmp/crowd.mov",
            proxy_path="/tmp/crowd.mov",
            duration_sec=20.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C001",
        )
        segments = [
            CandidateSegment(
                id="segment-1",
                asset_id="asset-1",
                start_sec=0.0,
                end_sec=5.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="First moment.",
                quality_metrics={"visual_novelty": 0.7, "subject_clarity": 0.8, "story_alignment": 0.65},
            ),
            CandidateSegment(
                id="segment-2",
                asset_id="asset-1",
                start_sec=5.0,
                end_sec=10.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Second moment.",
                quality_metrics={"visual_novelty": 0.8, "subject_clarity": 0.7, "story_alignment": 0.72},
            ),
            CandidateSegment(
                id="segment-3",
                asset_id="asset-1",
                start_sec=10.0,
                end_sec=15.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Third moment.",
                quality_metrics={"visual_novelty": 0.6, "subject_clarity": 0.75, "story_alignment": 0.68},
            ),
        ]

        evidence = build_segment_evidence(
            asset=asset,
            segment=segments[1],
            asset_segments=segments,
            segment_index=1,
            story_prompt="Build a warm opener.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        self.assertEqual(evidence.context_window_start_sec, 0.0)
        self.assertEqual(evidence.context_window_end_sec, 15.0)
        self.assertEqual(evidence.story_prompt, "Build a warm opener.")
        self.assertEqual(evidence.keyframe_paths, [])

    def test_deterministic_analyzer_returns_structured_output(self) -> None:
        asset = Asset(
            id="asset-2",
            name="Vendor Detail",
            source_path="/tmp/vendor.mov",
            proxy_path="/tmp/vendor.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C002",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-2",
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Vendor Detail provides a transition-ready moment.",
            quality_metrics={
                "visual_novelty": 0.82,
                "subject_clarity": 0.79,
                "story_alignment": 0.76,
                "motion_energy": 0.66,
                "duration_fit": 0.83,
            },
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a textured market sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        understanding = DeterministicVisionLanguageAnalyzer().analyze(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=evidence.story_prompt,
        )

        self.assertEqual(understanding.provider, "deterministic")
        self.assertTrue(understanding.summary)
        self.assertIn(understanding.keep_label, {"keep", "maybe", "reject"})
        self.assertTrue(0.0 <= understanding.confidence <= 1.0)

    def test_provider_status_defaults_to_deterministic(self) -> None:
        status = inspect_ai_provider_status(
            AIProviderConfig(
                provider="deterministic",
                model="",
                base_url="http://127.0.0.1:1234/v1",
                timeout_sec=30.0,
            )
        )

        self.assertEqual(status.effective_provider, "deterministic")
        self.assertTrue(status.available)

    def test_model_matches_handles_aliases(self) -> None:
        self.assertTrue(model_matches("qwen3.5-9b", "lmstudio-community/qwen3.5-9b"))
        self.assertTrue(model_matches("lmstudio-community/qwen3.5-9b", "qwen3.5-9b"))
        self.assertFalse(model_matches("qwen3.5-9b", "gemma-3-12b"))


if __name__ == "__main__":
    unittest.main()
