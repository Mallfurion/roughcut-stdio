from __future__ import annotations

import os
import unittest
import unittest.mock

from services.analyzer.app.domain import Asset
from services.analyzer.app.prefilter import (
    AudioSignal,
    AudioScreeningSummary,
    aggregate_segment_prefilter,
    build_audio_screening_summary,
    build_prefilter_segments,
    extract_gray_frames_batched,
    sample_asset_signals,
    sample_audio_signals,
    sample_timestamps,
    _fallback_audio_signals,
    _is_window_silent,
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

    def test_sample_asset_signals_uses_batched_extraction_and_preserves_order(self) -> None:
        asset = Asset(
            id="asset-batch",
            name="Batch Clip",
            source_path="/tmp/batch.mov",
            proxy_path="/tmp/batch.mov",
            duration_sec=24.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C020",
        )
        timestamps = [2.0, 6.0]
        frame_a = (2, 2, bytes([0, 64, 128, 255]))
        frame_b = (2, 2, bytes([255, 128, 64, 0]))

        with (
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frames_batched",
                return_value=[frame_a, frame_b],
            ) as batched_mock,
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frame",
                side_effect=AssertionError("single-frame extraction should not run"),
            ),
        ):
            signals = sample_asset_signals(asset, timestamps=timestamps, frame_width=32)

        self.assertEqual(batched_mock.call_count, 1)
        self.assertEqual([signal.timestamp_sec for signal in signals], timestamps)
        self.assertTrue(all(signal.source == "ffmpeg" for signal in signals))

    def test_sample_asset_signals_falls_back_to_single_extraction_when_batch_fails(self) -> None:
        asset = Asset(
            id="asset-batch-fallback",
            name="Batch Fallback Clip",
            source_path="/tmp/batch-fallback.mov",
            proxy_path="/tmp/batch-fallback.mov",
            duration_sec=24.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C021",
        )
        timestamps = [2.0, 6.0]
        frame_a = (2, 2, bytes([0, 64, 128, 255]))
        frame_b = (2, 2, bytes([255, 128, 64, 0]))

        with (
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frames_batched",
                return_value=None,
            ),
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frame",
                side_effect=[frame_a, frame_b],
            ) as single_mock,
        ):
            signals = sample_asset_signals(asset, timestamps=timestamps, frame_width=32)

        self.assertEqual(single_mock.call_count, len(timestamps))
        self.assertEqual([signal.timestamp_sec for signal in signals], timestamps)
        self.assertTrue(all(signal.source == "ffmpeg" for signal in signals))

    def test_batched_frame_sampling_matches_single_frame_metrics(self) -> None:
        asset = Asset(
            id="asset-batch-stability",
            name="Batch Stability Clip",
            source_path="/tmp/batch-stability.mov",
            proxy_path="/tmp/batch-stability.mov",
            duration_sec=24.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C022",
        )
        timestamps = [2.0, 6.0]
        frame_a = (2, 2, bytes([0, 64, 128, 255]))
        frame_b = (2, 2, bytes([255, 128, 64, 0]))

        with (
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frames_batched",
                return_value=[frame_a, frame_b],
            ),
            unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frame",
                side_effect=[frame_a, frame_b],
            ),
        ):
            batched_signals = sample_asset_signals(asset, timestamps=timestamps, frame_width=32)
            with unittest.mock.patch(
                "services.analyzer.app.prefilter.extract_gray_frames_batched",
                return_value=None,
            ):
                single_signals = sample_asset_signals(asset, timestamps=timestamps, frame_width=32)

        self.assertEqual(
            [(signal.timestamp_sec, signal.score, signal.motion_energy) for signal in batched_signals],
            [(signal.timestamp_sec, signal.score, signal.motion_energy) for signal in single_signals],
        )

    def test_extract_gray_frames_batched_returns_none_without_runtime(self) -> None:
        with unittest.mock.patch("services.analyzer.app.prefilter.shutil.which", return_value=None):
            self.assertIsNone(extract_gray_frames_batched("/tmp/missing.mov", [1.0, 2.0], width=64))


class AudioSignalTests(unittest.TestCase):
    def _make_asset(self, has_speech: bool = False) -> "Asset":
        from services.analyzer.app.domain import Asset
        return Asset(
            id="asset-audio",
            name="Audio Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=20.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=has_speech,
            interchange_reel_name="A001_C010",
        )

    def test_sample_audio_signals_returns_fallback_for_no_speech(self) -> None:
        asset = self._make_asset(has_speech=False)
        timestamps = sample_timestamps(asset.duration_sec)
        signals = sample_audio_signals(asset, timestamps)

        self.assertEqual(len(signals), len(timestamps))
        self.assertTrue(all(sig.source == "fallback" for sig in signals))
        self.assertTrue(all(sig.rms_energy == 0.0 for sig in signals))
        self.assertTrue(all(sig.is_silent for sig in signals))

    def test_build_audio_screening_summary_generates_shared_summary(self) -> None:
        asset = self._make_asset(has_speech=True)
        timestamps = [2.0, 6.0, 10.0]
        silence_intervals = [(0.0, 1.0), (8.0, 9.0)]
        rms_by_time = [(1.8, 0.01), (2.1, 0.02), (6.0, 0.03), (10.0, 0.0)]

        with (
            unittest.mock.patch("services.analyzer.app.prefilter.shutil.which", return_value="/usr/bin/ffmpeg"),
            unittest.mock.patch("services.analyzer.app.prefilter.Path.exists", return_value=True),
            unittest.mock.patch(
                "services.analyzer.app.prefilter._extract_audio_screening_data",
                return_value=(silence_intervals, rms_by_time),
            ),
        ):
            summary = build_audio_screening_summary(asset, timestamps)

        self.assertIsInstance(summary, AudioScreeningSummary)
        self.assertEqual(summary.source, "ffmpeg")
        self.assertEqual(summary.silence_intervals, silence_intervals)
        self.assertEqual(summary.rms_by_time, rms_by_time)
        self.assertEqual(len(summary.sampled_signals), len(timestamps))
        self.assertTrue(any(not signal.is_silent for signal in summary.sampled_signals))

    def test_sample_audio_signals_uses_shared_summary(self) -> None:
        asset = self._make_asset(has_speech=True)
        timestamps = [1.0, 3.0]
        summary = AudioScreeningSummary(
            timestamps=timestamps,
            silence_intervals=[],
            rms_by_time=[(1.0, 0.02), (3.0, 0.03)],
            sampled_signals=[
                AudioSignal(timestamp_sec=1.0, rms_energy=0.02, peak_loudness=0.02, is_silent=False, source="ffmpeg"),
                AudioSignal(timestamp_sec=3.0, rms_energy=0.03, peak_loudness=0.03, is_silent=False, source="ffmpeg"),
            ],
            source="ffmpeg",
        )

        with unittest.mock.patch(
            "services.analyzer.app.prefilter.build_audio_screening_summary",
            return_value=summary,
        ) as summary_mock:
            signals = sample_audio_signals(asset, timestamps)

        self.assertEqual(summary_mock.call_count, 1)
        self.assertEqual(signals, summary.sampled_signals)

    def test_sample_audio_signals_returns_fallback_for_missing_file(self) -> None:
        asset = self._make_asset(has_speech=True)
        timestamps = sample_timestamps(asset.duration_sec)
        signals = sample_audio_signals(asset, timestamps)

        self.assertEqual(len(signals), len(timestamps))
        self.assertTrue(all(sig.source == "fallback" for sig in signals))

    def test_sample_audio_signals_empty_timestamps(self) -> None:
        asset = self._make_asset(has_speech=True)
        signals = sample_audio_signals(asset, [])
        self.assertEqual(signals, [])

    def test_sample_audio_signals_disabled_via_env(self) -> None:
        asset = self._make_asset(has_speech=True)
        timestamps = sample_timestamps(asset.duration_sec)
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_AI_AUDIO_ENABLED": "false"}):
            signals = sample_audio_signals(asset, timestamps)
        self.assertEqual(len(signals), len(timestamps))
        self.assertTrue(all(sig.source == "fallback" for sig in signals))
        self.assertTrue(all(sig.rms_energy == 0.0 for sig in signals))

    def test_fallback_audio_signals_shape(self) -> None:
        timestamps = [1.0, 3.0, 5.0]
        signals = _fallback_audio_signals(timestamps)
        self.assertEqual(len(signals), 3)
        for sig, ts in zip(signals, timestamps):
            self.assertEqual(sig.timestamp_sec, ts)
            self.assertEqual(sig.rms_energy, 0.0)
            self.assertEqual(sig.peak_loudness, 0.0)
            self.assertTrue(sig.is_silent)
            self.assertEqual(sig.source, "fallback")

    def test_is_window_silent_fully_silent(self) -> None:
        intervals = [(0.0, 10.0)]
        self.assertTrue(_is_window_silent(intervals, 2.0, 6.0))

    def test_is_window_silent_not_silent(self) -> None:
        intervals = []
        self.assertFalse(_is_window_silent(intervals, 2.0, 6.0))

    def test_is_window_silent_partial_overlap(self) -> None:
        # Window is 4s wide, silence covers 1.5s (37.5%) — should not be silent
        intervals = [(3.0, 4.5)]
        self.assertFalse(_is_window_silent(intervals, 2.0, 6.0))

    def test_aggregate_segment_prefilter_includes_audio_metrics(self) -> None:
        from services.analyzer.app.domain import Asset
        asset = Asset(
            id="asset-1",
            name="Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C003",
        )
        visual_signals = sample_asset_signals(asset, target_count=5)
        audio_signals = [
            AudioSignal(timestamp_sec=3.0, rms_energy=0.4, peak_loudness=0.5, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=6.0, rms_energy=0.2, peak_loudness=0.3, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=9.0, rms_energy=0.0, peak_loudness=0.0, is_silent=True, source="ffmpeg"),
        ]
        snapshot = aggregate_segment_prefilter(
            signals=visual_signals,
            start_sec=2.0,
            end_sec=10.0,
            audio_signals=audio_signals,
        )
        metrics = snapshot["metrics_snapshot"]
        self.assertIn("audio_energy", metrics)
        self.assertIn("speech_ratio", metrics)
        self.assertGreater(metrics["audio_energy"], 0.0)
        # 2 of 3 matching signals are non-silent → speech_ratio = 2/3 ≈ 0.667
        self.assertAlmostEqual(metrics["speech_ratio"], 2 / 3, places=2)

    def test_aggregate_segment_prefilter_audio_fallback_zeros(self) -> None:
        from services.analyzer.app.domain import Asset
        asset = Asset(
            id="asset-1",
            name="Silent Clip",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C004",
        )
        visual_signals = sample_asset_signals(asset, target_count=5)
        snapshot = aggregate_segment_prefilter(
            signals=visual_signals,
            start_sec=2.0,
            end_sec=10.0,
            audio_signals=None,
        )
        metrics = snapshot["metrics_snapshot"]
        self.assertEqual(metrics["audio_energy"], 0.0)
        self.assertEqual(metrics["speech_ratio"], 0.0)

    def test_silent_asset_produces_zero_audio_in_scoring(self) -> None:
        from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision
        from services.analyzer.app.scoring import score_segment

        asset = Asset(
            id="asset-silent",
            name="Silent",
            source_path="/tmp/missing.mov",
            proxy_path="/tmp/missing.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C005",
        )
        segment = CandidateSegment(
            id="asset-silent-segment-01",
            asset_id="asset-silent",
            start_sec=0.0,
            end_sec=5.5,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Silent segment",
            quality_metrics={
                "sharpness": 0.6,
                "stability": 0.7,
                "visual_novelty": 0.5,
                "subject_clarity": 0.6,
                "motion_energy": 0.4,
                "duration_fit": 0.9,
                "audio_energy": 0.0,
                "speech_ratio": 0.0,
                "hook_strength": 0.5,
                "story_alignment": 0.5,
            },
            prefilter=PrefilterDecision(
                score=0.5,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="test",
                sampled_frame_count=3,
                sampled_frame_timestamps_sec=[1.0, 2.5, 4.0],
                top_frame_timestamps_sec=[2.5],
                metrics_snapshot={},
            ),
        )
        breakdown = score_segment(asset, segment)
        self.assertGreater(breakdown.total, 0.0)
        self.assertLessEqual(breakdown.total, 1.0)
        # audio_energy=0 in visual mode means same contribution as old speech_presence=0
        self.assertEqual(breakdown.analysis_mode, "visual")


if __name__ == "__main__":
    unittest.main()
