from __future__ import annotations

import unittest

from services.analyzer.app.analysis import analyze_assets, fallback_segments, inspect_runtime_capabilities
from services.analyzer.app.domain import Asset, ProjectMeta


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
        )

        silent_segments = [segment for segment in project.candidate_segments if segment.asset_id == "asset-1"]
        speech_segments = [segment for segment in project.candidate_segments if segment.asset_id == "asset-2"]
        best_takes = [take for take in project.take_recommendations if take.is_best_take]

        self.assertTrue(all(segment.analysis_mode == "visual" for segment in silent_segments))
        self.assertTrue(any(segment.analysis_mode == "speech" for segment in speech_segments))
        self.assertGreaterEqual(len(best_takes), 2)
        self.assertGreaterEqual(len(project.timeline.items), 2)

    def test_capabilities_are_reported_as_bools(self) -> None:
        capabilities = inspect_runtime_capabilities()
        self.assertTrue(all(isinstance(value, bool) for value in capabilities.values()))


if __name__ == "__main__":
    unittest.main()

