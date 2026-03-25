from __future__ import annotations

import unittest

from services.analyzer.app.domain import Asset, CandidateSegment
from services.analyzer.app.scoring import score_segment


class ScoreSegmentTests(unittest.TestCase):
    def test_silent_b_roll_uses_visual_mode(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Street Detail",
            source_path="/tmp/source.mov",
            proxy_path="/tmp/proxy.mov",
            duration_sec=15.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C001",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-1",
            start_sec=1.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Evening shoes cross a wet sidewalk.",
            quality_metrics={
                "sharpness": 0.78,
                "stability": 0.7,
                "visual_novelty": 0.88,
                "subject_clarity": 0.76,
                "motion_energy": 0.61,
                "duration_fit": 0.84,
                "audio_energy": 0.0,
                "speech_ratio": 0.0,
                "hook_strength": 0.74,
                "story_alignment": 0.86,
            },
        )

        breakdown = score_segment(asset, segment)

        self.assertEqual(breakdown.analysis_mode, "visual")
        self.assertGreater(breakdown.semantic, 0.7)
        self.assertGreater(breakdown.story, 0.75)
        self.assertGreater(breakdown.total, 0.7)

    def test_dialogue_uses_speech_features(self) -> None:
        asset = Asset(
            id="asset-2",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview-proxy.mov",
            duration_sec=30.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A002_C010",
        )
        segment = CandidateSegment(
            id="segment-2",
            asset_id="asset-2",
            start_sec=6.0,
            end_sec=11.0,
            analysis_mode="speech",
            transcript_excerpt="This is where the day starts moving.",
            description="Clean interview line about the turning point.",
            quality_metrics={
                "sharpness": 0.75,
                "stability": 0.72,
                "visual_novelty": 0.46,
                "subject_clarity": 0.84,
                "motion_energy": 0.3,
                "duration_fit": 0.9,
                "audio_energy": 0.85,
                "speech_ratio": 0.95,
                "hook_strength": 0.88,
                "story_alignment": 0.91,
            },
        )

        breakdown = score_segment(asset, segment)

        self.assertEqual(breakdown.analysis_mode, "speech")
        self.assertGreater(breakdown.semantic, 0.85)
        self.assertGreater(breakdown.total, 0.8)


if __name__ == "__main__":
    unittest.main()

