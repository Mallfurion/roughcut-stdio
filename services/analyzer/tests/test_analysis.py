from __future__ import annotations

import unittest

from services.analyzer.app.ai import DeterministicVisionLanguageAnalyzer
from services.analyzer.app.analysis import (
    analyze_assets,
    fallback_segments,
    inspect_runtime_capabilities,
    select_ai_target_segment_ids,
)
from services.analyzer.app.domain import Asset, CandidateSegment, ProjectMeta


class StaticSceneDetector:
    def __init__(self, segments: list[tuple[float, float]]) -> None:
        self.segments = segments

    def detect(self, asset: Asset) -> list[tuple[float, float]]:
        return self.segments


class StaticTranscriptProvider:
    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        if asset.has_speech and start_sec < 6:
            return "This is the line that turns the sequence."
        return ""


class ExpensiveAnalyzerStub:
    requires_keyframes = True

    def analyze(self, *, asset: Asset, segment: CandidateSegment, evidence, story_prompt: str):
        return DeterministicVisionLanguageAnalyzer().analyze(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )


class AnalysisPipelineTests(unittest.TestCase):
    def test_fallback_segments_cover_longer_clip(self) -> None:
        segments = fallback_segments(22.0)
        self.assertGreaterEqual(len(segments), 3)
        self.assertTrue(all(end > start for start, end in segments))

    def test_analyze_assets_supports_silent_and_speech_assets(self) -> None:
        assets = [
            Asset(
                id="asset-1",
                name="Street Wide",
                source_path="/tmp/street.mov",
                proxy_path="/tmp/street-proxy.mov",
                duration_sec=18.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C001",
            ),
            Asset(
                id="asset-2",
                name="Vendor Line",
                source_path="/tmp/vendor.mov",
                proxy_path="/tmp/vendor-proxy.mov",
                duration_sec=20.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=True,
                interchange_reel_name="A002_C014",
            ),
        ]

        project = analyze_assets(
            project=ProjectMeta(
                id="test-project",
                name="Test Project",
                story_prompt="Build a rough cut",
                status="draft",
                media_roots=["/tmp"],
            ),
            assets=assets,
            scene_detector=StaticSceneDetector([(0.0, 5.0), (5.0, 10.0)]),
            transcript_provider=StaticTranscriptProvider(),
            segment_analyzer=DeterministicVisionLanguageAnalyzer(),
        )

        silent_segments = [segment for segment in project.candidate_segments if segment.asset_id == "asset-1"]
        speech_segments = [segment for segment in project.candidate_segments if segment.asset_id == "asset-2"]
        best_takes = [take for take in project.take_recommendations if take.is_best_take]

        self.assertTrue(all(segment.analysis_mode == "visual" for segment in silent_segments))
        self.assertTrue(any(segment.analysis_mode == "speech" for segment in speech_segments))
        self.assertTrue(all(segment.evidence_bundle is not None for segment in project.candidate_segments))
        self.assertTrue(all(segment.ai_understanding is not None for segment in project.candidate_segments))
        self.assertTrue(all(segment.ai_understanding.provider for segment in project.candidate_segments if segment.ai_understanding))
        self.assertGreaterEqual(len(best_takes), 2)
        self.assertGreaterEqual(len(project.timeline.items), 2)

    def test_capabilities_are_reported_as_bools(self) -> None:
        capabilities = inspect_runtime_capabilities()
        self.assertTrue(all(isinstance(value, bool) for value in capabilities.values()))

    def test_fast_mode_shortlists_top_segments_for_expensive_analyzer(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Street Wide",
            source_path="/tmp/street.mov",
            proxy_path="/tmp/street.mov",
            duration_sec=18.0,
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
                description="One",
                quality_metrics={"visual_novelty": 0.6, "subject_clarity": 0.7, "story_alignment": 0.62, "motion_energy": 0.5, "duration_fit": 0.8, "hook_strength": 0.6},
            ),
            CandidateSegment(
                id="segment-2",
                asset_id="asset-1",
                start_sec=5.0,
                end_sec=10.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Two",
                quality_metrics={"visual_novelty": 0.85, "subject_clarity": 0.84, "story_alignment": 0.78, "motion_energy": 0.74, "duration_fit": 0.82, "hook_strength": 0.8},
            ),
            CandidateSegment(
                id="segment-3",
                asset_id="asset-1",
                start_sec=10.0,
                end_sec=15.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Three",
                quality_metrics={"visual_novelty": 0.82, "subject_clarity": 0.79, "story_alignment": 0.76, "motion_energy": 0.68, "duration_fit": 0.8, "hook_strength": 0.77},
            ),
        ]

        target_ids = select_ai_target_segment_ids(
            asset=asset,
            segments=segments,
            analyzer=ExpensiveAnalyzerStub(),
            max_segments_per_asset=2,
            mode="fast",
        )

        self.assertEqual(len(target_ids), 2)
        self.assertIn("segment-2", target_ids)
        self.assertIn("segment-3", target_ids)


if __name__ == "__main__":
    unittest.main()
