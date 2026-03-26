from __future__ import annotations

import unittest

from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision
from services.analyzer.app.scoring import infer_analysis_mode, limiting_factor_labels, score_segment, top_score_driver_labels


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
        self.assertGreater(breakdown.total, 0.79)

    def test_speech_signal_fallback_uses_speech_mode_without_transcript(self) -> None:
        asset = Asset(
            id="asset-2b",
            name="Speech Test",
            source_path="/tmp/speech.mov",
            proxy_path="/tmp/speech-proxy.mov",
            duration_sec=16.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A002_C011",
        )
        segment = CandidateSegment(
            id="segment-2b",
            asset_id="asset-2b",
            start_sec=6.0,
            end_sec=11.0,
            analysis_mode="speech",
            transcript_excerpt="",
            description="Speech fallback beat.",
            quality_metrics={
                "sharpness": 0.62,
                "stability": 0.68,
                "visual_novelty": 0.4,
                "subject_clarity": 0.78,
                "motion_energy": 0.24,
                "duration_fit": 0.84,
                "audio_energy": 0.46,
                "speech_ratio": 1.0,
                "hook_strength": 0.71,
                "story_alignment": 0.74,
            },
        )

        analysis_mode, source = infer_analysis_mode(asset, segment.transcript_excerpt, segment.quality_metrics)
        breakdown = score_segment(asset, segment)

        self.assertEqual(analysis_mode, "speech")
        self.assertEqual(source, "speech-signal-fallback")
        self.assertEqual(breakdown.analysis_mode, "speech")
        self.assertGreater(breakdown.total, 0.6)

    def test_complete_turn_scores_above_truncated_turn(self) -> None:
        asset = Asset(
            id="asset-turn",
            name="Interview Turn",
            source_path="/tmp/interview-turn.mov",
            proxy_path="/tmp/interview-turn-proxy.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A002_C012",
        )
        complete = CandidateSegment(
            id="segment-complete",
            asset_id=asset.id,
            start_sec=2.0,
            end_sec=6.0,
            analysis_mode="speech",
            transcript_excerpt="We start with the question and carry the answer through.",
            description="Complete spoken beat.",
            quality_metrics={
                "sharpness": 0.74,
                "stability": 0.7,
                "visual_novelty": 0.45,
                "subject_clarity": 0.83,
                "motion_energy": 0.28,
                "duration_fit": 0.88,
                "audio_energy": 0.78,
                "speech_ratio": 0.94,
                "hook_strength": 0.82,
                "story_alignment": 0.87,
                "turn_completeness": 0.95,
            },
        )
        truncated = CandidateSegment(
            id="segment-truncated",
            asset_id=asset.id,
            start_sec=2.5,
            end_sec=5.2,
            analysis_mode="speech",
            transcript_excerpt="carry the answer through",
            description="Truncated spoken beat.",
            quality_metrics={
                "sharpness": 0.74,
                "stability": 0.7,
                "visual_novelty": 0.45,
                "subject_clarity": 0.83,
                "motion_energy": 0.28,
                "duration_fit": 0.88,
                "audio_energy": 0.78,
                "speech_ratio": 0.94,
                "hook_strength": 0.82,
                "story_alignment": 0.87,
                "turn_completeness": 0.42,
            },
        )

        complete_score = score_segment(asset, complete)
        truncated_score = score_segment(asset, truncated)

        self.assertGreater(complete_score.semantic, truncated_score.semantic)
        self.assertGreater(complete_score.story, truncated_score.story)
        self.assertGreater(complete_score.total, truncated_score.total)

    def test_top_score_driver_labels_follow_weighted_formula(self) -> None:
        asset = Asset(
            id="asset-3",
            name="Market Dialogue",
            source_path="/tmp/market.mov",
            proxy_path="/tmp/market-proxy.mov",
            duration_sec=22.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A003_C003",
        )
        segment = CandidateSegment(
            id="segment-3",
            asset_id="asset-3",
            start_sec=2.0,
            end_sec=7.0,
            analysis_mode="speech",
            transcript_excerpt="The day starts here.",
            description="Strong speech beat.",
            quality_metrics={
                "sharpness": 0.73,
                "stability": 0.7,
                "visual_novelty": 0.44,
                "subject_clarity": 0.84,
                "motion_energy": 0.32,
                "duration_fit": 0.9,
                "audio_energy": 0.81,
                "speech_ratio": 0.93,
                "hook_strength": 0.91,
                "story_alignment": 0.95,
            },
            prefilter=PrefilterDecision(
                score=0.88,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="Shortlisted.",
                sampled_frame_count=3,
                sampled_frame_timestamps_sec=[2.5, 4.0, 6.0],
                top_frame_timestamps_sec=[4.0],
                metrics_snapshot={"clip_score": 0.71},
            ),
        )

        drivers = top_score_driver_labels(asset, segment)

        self.assertIn("story alignment", drivers)
        self.assertIn("hook strength", drivers)
        self.assertEqual(len(drivers), 3)

    def test_limiting_factor_labels_compare_against_winner(self) -> None:
        asset = Asset(
            id="asset-4",
            name="Street Coverage",
            source_path="/tmp/street.mov",
            proxy_path="/tmp/street-proxy.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A004_C002",
        )
        winner = CandidateSegment(
            id="winner",
            asset_id="asset-4",
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Winner",
            quality_metrics={
                "sharpness": 0.84,
                "stability": 0.78,
                "visual_novelty": 0.91,
                "subject_clarity": 0.82,
                "motion_energy": 0.86,
                "duration_fit": 0.88,
                "audio_energy": 0.0,
                "speech_ratio": 0.0,
                "hook_strength": 0.85,
                "story_alignment": 0.89,
            },
        )
        backup = CandidateSegment(
            id="backup",
            asset_id="asset-4",
            start_sec=5.0,
            end_sec=10.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Backup",
            quality_metrics={
                "sharpness": 0.82,
                "stability": 0.74,
                "visual_novelty": 0.62,
                "subject_clarity": 0.8,
                "motion_energy": 0.48,
                "duration_fit": 0.84,
                "audio_energy": 0.0,
                "speech_ratio": 0.0,
                "hook_strength": 0.57,
                "story_alignment": 0.66,
            },
        )

        limiting = limiting_factor_labels(asset, backup, winner)

        self.assertIn("visual novelty", limiting)
        self.assertIn("motion energy", limiting)


if __name__ == "__main__":
    unittest.main()
