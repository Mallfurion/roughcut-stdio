from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.analyzer.app.deduplication import (
    HistogramSimilarity,
    apply_deduplication_results,
    deduplicate_segments,
    get_dedup_threshold,
    is_deduplication_enabled,
)
from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision
from services.analyzer.app.prefilter import FrameSignal


class TestHistogramSimilarity(unittest.TestCase):
    """Tests for histogram-based similarity computation."""

    def setUp(self) -> None:
        """Set up test data."""
        self.asset = Asset(
            id="test-asset",
            name="test.mov",
            source_path="/source/test.mov",
            proxy_path="/proxy/test.mov",
            duration_sec=10.0,
            fps=24,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A1",
        )

    def _make_segment(
        self,
        seg_id: str,
        start_sec: float = 0.0,
        end_sec: float = 5.0,
        score: float = 0.5,
    ) -> CandidateSegment:
        return CandidateSegment(
            id=seg_id,
            asset_id=self.asset.id,
            start_sec=start_sec,
            end_sec=end_sec,
            analysis_mode="visual",
            transcript_excerpt="",
            description="",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=score,
                shortlisted=False,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[start_sec + (end_sec - start_sec) / 2],
                top_frame_timestamps_sec=[start_sec + (end_sec - start_sec) / 2],
                metrics_snapshot={},
            ),
        )

    def _make_signals(self, brightness: float, distinctiveness: float, count: int = 3) -> list[FrameSignal]:
        return [
            FrameSignal(
                timestamp_sec=float(i),
                sharpness=0.5,
                contrast=0.5,
                brightness=brightness,
                motion_energy=0.3,
                distinctiveness=distinctiveness,
                center_focus=0.5,
                score=0.5,
                source="test",
            )
            for i in range(count)
        ]

    def test_histogram_similarity_identical_segments(self) -> None:
        """Test similarity between identical segments."""
        signals1 = self._make_signals(brightness=0.5, distinctiveness=0.6)
        signals2 = self._make_signals(brightness=0.5, distinctiveness=0.6)

        frame_signals = {
            "segment-1": signals1,
            "segment-2": signals2,
        }
        similarity = HistogramSimilarity(frame_signals)

        seg1 = self._make_segment("segment-1")
        seg2 = self._make_segment("segment-2")

        similarity_score = similarity.compute_similarity(seg1, seg2)
        self.assertGreater(similarity_score, 0.8, "Similar segments should have high similarity")

    def test_histogram_similarity_different_segments(self) -> None:
        """Test similarity between different segments."""
        signals1 = self._make_signals(brightness=0.2, distinctiveness=0.4)
        signals2 = self._make_signals(brightness=0.8, distinctiveness=0.9)

        frame_signals = {
            "segment-1": signals1,
            "segment-2": signals2,
        }
        similarity = HistogramSimilarity(frame_signals)

        seg1 = self._make_segment("segment-1")
        seg2 = self._make_segment("segment-2")

        similarity_score = similarity.compute_similarity(seg1, seg2)
        self.assertLess(similarity_score, 0.7, "Different segments should have low similarity")

    def test_histogram_similarity_missing_signals(self) -> None:
        """Test similarity when signals are missing."""
        frame_signals: dict[str, list[FrameSignal]] = {}
        similarity = HistogramSimilarity(frame_signals)

        seg1 = self._make_segment("segment-1")
        seg2 = self._make_segment("segment-2")

        similarity_score = similarity.compute_similarity(seg1, seg2)
        self.assertEqual(similarity_score, 0.0, "Missing signals should return 0 similarity")

    def test_histogram_caching(self) -> None:
        """Test that histograms are cached."""
        signals = self._make_signals(brightness=0.5, distinctiveness=0.6)
        frame_signals = {
            "segment-1": signals,
            "segment-2": signals,
        }
        similarity = HistogramSimilarity(frame_signals)

        seg1 = self._make_segment("segment-1")
        seg2 = self._make_segment("segment-2")

        # First call computes histograms
        similarity.compute_similarity(seg1, seg2)
        cache_size_after_first = len(similarity._histogram_cache)

        # Second call should use cache
        similarity.compute_similarity(seg1, seg2)
        cache_size_after_second = len(similarity._histogram_cache)

        self.assertEqual(cache_size_after_first, cache_size_after_second, "Cache size should not change")


class TestDeduplicateSegments(unittest.TestCase):
    """Tests for segment deduplication logic."""

    def setUp(self) -> None:
        """Set up test data."""
        self.asset = Asset(
            id="test-asset",
            name="test.mov",
            source_path="/source/test.mov",
            proxy_path="/proxy/test.mov",
            duration_sec=10.0,
            fps=24,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A1",
        )

    def _make_segment(self, seg_id: str, score: float = 0.5) -> CandidateSegment:
        return CandidateSegment(
            id=seg_id,
            asset_id=self.asset.id,
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=score,
                shortlisted=False,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[2.5],
                top_frame_timestamps_sec=[2.5],
                metrics_snapshot={},
            ),
        )

    def test_deduplicate_single_segment(self) -> None:
        """Test deduplication with single segment."""
        seg1 = self._make_segment("segment-1", score=0.8)
        frame_signals_by_id: dict[str, list[FrameSignal]] = {}

        results = deduplicate_segments([seg1], frame_signals_by_id)

        self.assertEqual(len(results), 1)
        self.assertFalse(results["segment-1"][0], "Single segment should not be deduplicated")
        self.assertEqual(results["segment-1"][1], 0, "Single segment should have group 0")

    def test_deduplicate_no_duplicates(self) -> None:
        """Test deduplication with no duplicates found."""
        seg1 = self._make_segment("segment-1", score=0.8)
        seg2 = self._make_segment("segment-2", score=0.7)
        frame_signals_by_id: dict[str, list[FrameSignal]] = {}

        results = deduplicate_segments([seg1, seg2], frame_signals_by_id)

        self.assertEqual(len(results), 2)
        self.assertFalse(results["segment-1"][0], "Higher-scoring segment should not be deduplicated")
        self.assertFalse(results["segment-2"][0], "Lower-scoring segment should not be deduplicated")

    def test_deduplicate_respects_score_order(self) -> None:
        """Test that deduplication keeps highest-scoring segment."""
        seg1 = self._make_segment("segment-1", score=0.9)
        seg2 = self._make_segment("segment-2", score=0.5)
        seg3 = self._make_segment("segment-3", score=0.7)

        frame_signals_by_id: dict[str, list[FrameSignal]] = {}
        results = deduplicate_segments(
            [seg1, seg2, seg3],
            frame_signals_by_id,
            similarity_threshold=0.0,  # Make all similar
        )

        # seg1 has highest score, should not be deduplicated
        self.assertFalse(results["segment-1"][0], "Highest-scoring segment should not be deduplicated")

    def test_deduplicate_groups_segments(self) -> None:
        """Test that deduplicated segments have the same group ID."""
        seg1 = self._make_segment("segment-1", score=0.9)
        seg2 = self._make_segment("segment-2", score=0.5)

        frame_signals_by_id: dict[str, list[FrameSignal]] = {}
        results = deduplicate_segments(
            [seg1, seg2],
            frame_signals_by_id,
            similarity_threshold=0.0,  # Make all similar
        )

        self.assertEqual(results["segment-1"][1], results["segment-2"][1], "Similar segments should have same group ID")


class TestApplyDeduplicationResults(unittest.TestCase):
    """Tests for applying deduplication results."""

    def setUp(self) -> None:
        """Set up test data."""
        self.asset = Asset(
            id="test-asset",
            name="test.mov",
            source_path="/source/test.mov",
            proxy_path="/proxy/test.mov",
            duration_sec=10.0,
            fps=24,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A1",
        )

    def _make_segment(self, seg_id: str) -> CandidateSegment:
        return CandidateSegment(
            id=seg_id,
            asset_id=self.asset.id,
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=0.5,
                shortlisted=False,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[2.5],
                top_frame_timestamps_sec=[2.5],
                metrics_snapshot={},
            ),
        )

    def test_apply_results_sets_flags(self) -> None:
        """Test that results are applied to segments."""
        seg1 = self._make_segment("segment-1")
        seg2 = self._make_segment("segment-2")
        segments = [seg1, seg2]

        dedup_results = {
            "segment-1": (False, 0),
            "segment-2": (True, 0),
        }
        apply_deduplication_results(segments, dedup_results)

        self.assertFalse(seg1.prefilter.deduplicated, "Kept segment should not be deduplicated")
        self.assertEqual(seg1.prefilter.dedup_group_id, 0, "Kept segment should have group ID")

        self.assertTrue(seg2.prefilter.deduplicated, "Removed segment should be deduplicated")
        self.assertEqual(seg2.prefilter.dedup_group_id, 0, "Removed segment should have group ID")

    def test_apply_results_handles_missing_prefilter(self) -> None:
        """Test that apply results handles segments without prefilter."""
        seg = CandidateSegment(
            id="segment-1",
            asset_id=self.asset.id,
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="",
            quality_metrics={},
            prefilter=None,
        )
        segments = [seg]

        dedup_results = {"segment-1": (False, 0)}
        # Should not raise
        apply_deduplication_results(segments, dedup_results)

        self.assertIsNone(seg.prefilter, "Segment without prefilter should remain unchanged")


class TestEnvironmentVariables(unittest.TestCase):
    """Tests for environment variable handling."""

    def test_is_deduplication_enabled_default(self) -> None:
        """Test that deduplication is enabled by default."""
        with patch.dict("os.environ", {}, clear=False):
            if "TIMELINE_DEDUPLICATION_ENABLED" in os.environ:
                del os.environ["TIMELINE_DEDUPLICATION_ENABLED"]
            self.assertTrue(is_deduplication_enabled(), "Deduplication should be enabled by default")

    def test_is_deduplication_enabled_explicit_true(self) -> None:
        """Test deduplication enabled with explicit true."""
        with patch.dict("os.environ", {"TIMELINE_DEDUPLICATION_ENABLED": "true"}):
            self.assertTrue(is_deduplication_enabled())

    def test_is_deduplication_enabled_explicit_false(self) -> None:
        """Test deduplication disabled."""
        with patch.dict("os.environ", {"TIMELINE_DEDUPLICATION_ENABLED": "false"}):
            self.assertFalse(is_deduplication_enabled())

    def test_get_dedup_threshold_default(self) -> None:
        """Test default threshold."""
        with patch.dict("os.environ", {}, clear=False):
            if "TIMELINE_DEDUP_THRESHOLD" in os.environ:
                del os.environ["TIMELINE_DEDUP_THRESHOLD"]
            self.assertEqual(get_dedup_threshold(), 0.85, "Default threshold should be 0.85")

    def test_get_dedup_threshold_custom(self) -> None:
        """Test custom threshold."""
        with patch.dict("os.environ", {"TIMELINE_DEDUP_THRESHOLD": "0.75"}):
            self.assertEqual(get_dedup_threshold(), 0.75)

    def test_get_dedup_threshold_invalid(self) -> None:
        """Test invalid threshold falls back to default."""
        with patch.dict("os.environ", {"TIMELINE_DEDUP_THRESHOLD": "invalid"}):
            self.assertEqual(get_dedup_threshold(), 0.85, "Invalid threshold should fall back to default")


if __name__ == "__main__":
    unittest.main()
