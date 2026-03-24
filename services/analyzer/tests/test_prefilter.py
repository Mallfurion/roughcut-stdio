from __future__ import annotations

import unittest

from services.analyzer.app.domain import Asset
from services.analyzer.app.prefilter import (
    aggregate_segment_prefilter,
    build_prefilter_segments,
    sample_asset_signals,
    sample_timestamps,
)


class PrefilterTests(unittest.TestCase):
    def test_sample_timestamps_scale_with_duration(self) -> None:
        timestamps = sample_timestamps(48.0)
        self.assertGreaterEqual(len(timestamps), 6)
        self.assertTrue(all(later > earlier for earlier, later in zip(timestamps, timestamps[1:])))

    def test_sample_asset_signals_falls_back_deterministically(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Fallback Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=24.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C001",
        )

        signals = sample_asset_signals(asset, target_count=5)

        self.assertEqual(len(signals), 5)
        self.assertTrue(all(0.0 <= signal.score <= 1.0 for signal in signals))

    def test_build_prefilter_segments_adds_peak_windows(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Peak Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=30.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C002",
        )
        signals = sample_asset_signals(asset, target_count=6)
        segments = build_prefilter_segments(
            asset=asset,
            base_ranges=[(0.0, 30.0)],
            signals=signals,
            top_windows=2,
        )

        self.assertTrue(segments)
        self.assertTrue(all(end > start for start, end in segments))

    def test_aggregate_segment_prefilter_returns_metrics_snapshot(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Aggregate Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C003",
        )
        signals = sample_asset_signals(asset, target_count=5)
        snapshot = aggregate_segment_prefilter(signals=signals, start_sec=2.0, end_sec=10.0)

        self.assertGreater(snapshot["sampled_frame_count"], 0)
        self.assertIn("prefilter_score", snapshot["metrics_snapshot"])


if __name__ == "__main__":
    unittest.main()
