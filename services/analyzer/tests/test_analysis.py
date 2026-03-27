from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import unittest.mock

from services.analyzer.app.ai import DeterministicVisionLanguageAnalyzer, load_ai_analysis_config
from services.analyzer.app.analysis import (
    FasterWhisperAdapter,
    NoOpTranscriptProvider,
    RefinedSegmentCandidate,
    TranscriptSpan,
    derive_transcript_turns,
    analyze_assets,
    assemble_narrative_units,
    build_transcript_provider,
    build_timeline,
    build_segment_review_state,
    build_take_recommendations,
    build_transcript_probe_ranges,
    fallback_segments,
    inspect_runtime_capabilities,
    make_candidate_segment,
    should_request_transcript_for_asset,
    should_probe_after_selective_skip,
    should_probe_before_full_transcript,
    semantic_boundary_ambiguity_score,
    suggested_timeline_duration,
    select_ai_target_segment_ids,
    select_prefilter_shortlist_ids,
    transcript_runtime_status,
)
from services.analyzer.app.domain import Asset, BoundaryValidationResult, CandidateSegment, PrefilterDecision, ProjectData, ProjectMeta, TakeRecommendation, Timeline, TimelineItem
from services.analyzer.app.prefilter import AudioSignal, FrameSignal, SeedRegion
from services.analyzer.app.service import load_project


ROOT = Path(__file__).resolve().parents[3]
REVIEW_FIXTURE = ROOT / "fixtures" / "review-states-project.json"


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


class TimedTranscriptProvider:
    def __init__(self, spans: list[TranscriptSpan]) -> None:
        self._spans = spans

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list[TranscriptSpan]:
        return [
            span
            for span in self._spans
            if span.end_sec >= start_sec and span.start_sec <= end_sec
        ]

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        return " ".join(span.text for span in self.spans(asset, start_sec, end_sec)).strip()

    def runtime_status(self):
        return transcript_runtime_status(NoOpTranscriptProvider())

    def has_cached_asset(self, asset: Asset) -> bool:
        return False


class ExcerptOnlyTranscriptProvider:
    def __init__(self) -> None:
        self.called = False

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        self.called = True
        return "Should not be used."

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list[TranscriptSpan]:
        return []

    def runtime_status(self):
        return transcript_runtime_status(NoOpTranscriptProvider())

    def has_cached_asset(self, asset: Asset) -> bool:
        return False


class ProbeAwareTranscriptProvider:
    def __init__(self, *, probe_accepts: bool, spans: list[TranscriptSpan] | None = None) -> None:
        self.probe_accepts = probe_accepts
        self._spans = spans or []
        self.probe_calls = 0
        self.spans_calls = 0

    def probe(self, asset: Asset, clip_ranges: list[tuple[float, float]]) -> bool:
        self.probe_calls += 1
        return self.probe_accepts

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        spans = self.spans(asset, start_sec, end_sec)
        return " ".join(span.text for span in spans).strip()

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list[TranscriptSpan]:
        self.spans_calls += 1
        return [
            span
            for span in self._spans
            if span.end_sec >= start_sec and span.start_sec <= end_sec
        ]

    def runtime_status(self):
        return NoOpTranscriptProvider(
            configured_provider="auto",
            effective_provider="faster-whisper",
            model_size="small",
            enabled=True,
            available=True,
            status="active",
            detail="active",
        ).runtime_status()

    def has_cached_asset(self, asset: Asset) -> bool:
        return False


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
        shortlisted_segments = [segment for segment in project.candidate_segments if segment.prefilter and segment.prefilter.shortlisted]

        self.assertTrue(all(segment.analysis_mode == "visual" for segment in silent_segments))
        self.assertTrue(any(segment.analysis_mode == "speech" for segment in speech_segments))
        self.assertTrue(all(segment.evidence_bundle is not None for segment in shortlisted_segments))
        self.assertTrue(all(segment.prefilter is not None for segment in project.candidate_segments))
        self.assertTrue(all(segment.ai_understanding is not None for segment in shortlisted_segments))
        self.assertTrue(all(segment.ai_understanding.provider for segment in shortlisted_segments if segment.ai_understanding))
        self.assertGreaterEqual(len(best_takes), 2)
        self.assertGreaterEqual(len(project.timeline.items), 2)
        self.assertGreater(project.project.analysis_summary.get("prefilter_sample_count", 0), 0)
        self.assertEqual(project.project.analysis_summary.get("ai_live_segment_count", 0), 0)
        self.assertEqual(project.project.analysis_summary.get("ai_cached_segment_count", 0), 0)
        self.assertEqual(project.project.analysis_summary.get("ai_fallback_segment_count", 0), 0)
        phase_timings = project.project.analysis_summary.get("phase_timings_sec", {})
        self.assertIn("per_asset_analysis", phase_timings)
        self.assertIn("take_selection", phase_timings)
        self.assertIn("timeline_assembly", phase_timings)
        self.assertTrue(all(phase_timings[key] >= 0.0 for key in phase_timings))

    def test_capabilities_are_reported_as_bools(self) -> None:
        capabilities = inspect_runtime_capabilities()
        self.assertTrue(all(isinstance(value, bool) for value in capabilities.values()))

    def test_build_transcript_provider_reports_disabled_or_unavailable(self) -> None:
        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_TRANSCRIPT_PROVIDER": "disabled",
                "TIMELINE_TRANSCRIPT_MODEL_SIZE": "base",
            },
            clear=False,
        ):
            disabled_provider = build_transcript_provider(load_ai_analysis_config())
        disabled_status = disabled_provider.runtime_status()
        self.assertEqual(disabled_status.status, "disabled")
        self.assertFalse(disabled_status.enabled)

        with (
            unittest.mock.patch.dict(
                os.environ,
                {
                    "TIMELINE_TRANSCRIPT_PROVIDER": "auto",
                    "TIMELINE_TRANSCRIPT_MODEL_SIZE": "small",
                },
                clear=False,
            ),
            unittest.mock.patch("services.analyzer.app.analysis.importlib.util.find_spec", return_value=None),
        ):
            unavailable_provider = build_transcript_provider(load_ai_analysis_config())
        unavailable_status = unavailable_provider.runtime_status()
        self.assertEqual(unavailable_status.status, "unavailable")
        self.assertTrue(unavailable_status.enabled)
        self.assertFalse(unavailable_status.available)

    def test_faster_whisper_adapter_persistent_cache_round_trips_spans(self) -> None:
        with TemporaryDirectory() as temp_dir:
            proxy_path = Path(temp_dir) / "sample.mov"
            proxy_path.write_bytes(b"placeholder")
            asset = Asset(
                id="asset-cache",
                name="Cache Test",
                source_path=str(proxy_path),
                proxy_path=str(proxy_path),
                duration_sec=8.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=True,
                interchange_reel_name="A999_C001",
            )
            adapter = FasterWhisperAdapter(model_size="small", cache_root=temp_dir)
            spans = [TranscriptSpan(start_sec=1.0, end_sec=2.5, text="Cached line.")]

            adapter._write_cached_spans(asset, spans)
            loaded = adapter._load_cached_spans(asset)

            self.assertTrue(loaded)
            self.assertEqual(adapter._cache[asset.proxy_path][0].text, "Cached line.")
            self.assertEqual(adapter.runtime_status().cached_asset_count, 1)

    def test_make_candidate_segment_uses_speech_fallback_without_transcript(self) -> None:
        asset = Asset(
            id="asset-speech",
            name="IMG_8660",
            source_path="/tmp/speech.mov",
            proxy_path="/tmp/speech-proxy.mov",
            duration_sec=15.6,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A007_C001",
        )
        segment = make_candidate_segment(
            asset=asset,
            segment_id="asset-speech-segment-01",
            start_sec=10.4,
            end_sec=15.6,
            transcriber=NoOpTranscriptProvider(),
            transcript_spans=[],
            transcript_turns=[],
            prefilter_signals=[
                FrameSignal(11.0, 0.7, 0.6, 0.5, 0.22, 0.45, 0.7, 0.64, "deterministic"),
                FrameSignal(13.0, 0.72, 0.62, 0.48, 0.18, 0.43, 0.72, 0.63, "deterministic"),
            ],
            audio_signals=[
                AudioSignal(11.0, 0.44, 0.5, False, "ffmpeg"),
                AudioSignal(13.0, 0.48, 0.55, False, "ffmpeg"),
            ],
            boundary_strategy="scene-snap",
            boundary_confidence=0.8,
            seed_region_ids=["seed-01"],
            seed_region_sources=["scene"],
            seed_region_ranges_sec=[[10.4, 15.6]],
        )

        self.assertEqual(segment.analysis_mode, "speech")
        self.assertEqual(segment.transcript_excerpt, "")
        self.assertIn("transcript text is unavailable", segment.description)

    def test_make_candidate_segment_skip_does_not_lazy_load_transcript(self) -> None:
        asset = Asset(
            id="asset-skip",
            name="Skip Test",
            source_path="/tmp/skip.mov",
            proxy_path="/tmp/skip.mov",
            duration_sec=6.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A008_C001",
        )
        provider = ExcerptOnlyTranscriptProvider()
        segment = make_candidate_segment(
            asset=asset,
            segment_id="asset-skip-segment-01",
            start_sec=0.0,
            end_sec=4.0,
            transcriber=provider,
            transcript_spans=[],
            transcript_turns=[],
            prefilter_signals=[FrameSignal(1.0, 0.7, 0.6, 0.5, 0.2, 0.4, 0.7, 0.6, "deterministic")],
            audio_signals=[AudioSignal(1.0, 0.002, 0.0, True, "ffmpeg")],
            boundary_strategy="legacy",
            boundary_confidence=0.0,
            seed_region_ids=[],
            seed_region_sources=[],
            seed_region_ranges_sec=[],
            transcript_lookup_enabled=False,
        )

        self.assertFalse(provider.called)
        self.assertEqual(segment.transcript_excerpt, "")

    def test_derive_transcript_turns_groups_adjacent_spans(self) -> None:
        turns = derive_transcript_turns(
            [
                TranscriptSpan(1.0, 1.8, "How do we start?"),
                TranscriptSpan(2.0, 3.1, "Start with the strongest frame."),
                TranscriptSpan(5.0, 6.2, "Then hold on the answer."),
            ]
        )

        self.assertEqual(len(turns), 2)
        self.assertEqual((turns[0].start_sec, turns[0].end_sec), (1.0, 3.1))
        self.assertEqual(turns[0].id, "turn-01")
        self.assertIn("strongest frame", turns[0].text)

    def test_should_request_transcript_for_asset_uses_selective_thresholds(self) -> None:
        asset = Asset(
            id="asset-selective",
            name="Selective Test",
            source_path="/tmp/selective.mov",
            proxy_path="/tmp/selective.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A010_C001",
        )
        runtime_status = NoOpTranscriptProvider(
            configured_provider="auto",
            effective_provider="faster-whisper",
            model_size="small",
            enabled=True,
            available=True,
            status="active",
            detail="active",
        ).runtime_status()

        should_skip = should_request_transcript_for_asset(
            asset=asset,
            audio_signals=[
                AudioSignal(1.0, 0.003, 0.0, True, "ffmpeg"),
                AudioSignal(3.0, 0.004, 0.0, True, "ffmpeg"),
                AudioSignal(5.0, 0.005, 0.0, False, "ffmpeg"),
                AudioSignal(7.0, 0.004, 0.0, True, "ffmpeg"),
            ],
            transcriber=NoOpTranscriptProvider(),
            runtime_status=runtime_status,
        )
        should_transcribe = should_request_transcript_for_asset(
            asset=asset,
            audio_signals=[
                AudioSignal(1.0, 0.055, 0.0, False, "ffmpeg"),
                AudioSignal(3.0, 0.038, 0.0, False, "ffmpeg"),
                AudioSignal(5.0, 0.074, 0.0, False, "ffmpeg"),
                AudioSignal(7.0, 0.047, 0.0, False, "ffmpeg"),
            ],
            transcriber=NoOpTranscriptProvider(),
            runtime_status=runtime_status,
        )

        self.assertFalse(should_skip)
        self.assertTrue(should_transcribe)

    def test_borderline_transcript_candidates_use_probe_ranges(self) -> None:
        asset = Asset(
            id="asset-probe",
            name="Probe Test",
            source_path="/tmp/probe.mov",
            proxy_path="/tmp/probe.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A011_C001",
        )
        audio_signals = [
            AudioSignal(1.0, 0.009, 0.0, False, "ffmpeg"),
            AudioSignal(4.0, 0.006, 0.0, False, "ffmpeg"),
            AudioSignal(8.0, 0.014, 0.0, False, "ffmpeg"),
            AudioSignal(10.0, 0.008, 0.0, False, "ffmpeg"),
        ]

        self.assertTrue(should_probe_before_full_transcript(audio_signals))
        self.assertEqual(
            build_transcript_probe_ranges(asset, audio_signals),
            [(0.0, 4.0), (6.0, 10.0)],
        )

    def test_selective_skip_assets_can_still_trigger_probe(self) -> None:
        low_speech_audio = [
            AudioSignal(1.0, 0.0029, 0.0, True, "ffmpeg"),
            AudioSignal(3.0, 0.0031, 0.0, True, "ffmpeg"),
            AudioSignal(5.0, 0.0091, 0.0, False, "ffmpeg"),
            AudioSignal(7.0, 0.005, 0.0, False, "ffmpeg"),
        ]
        silent_audio = [
            AudioSignal(1.0, 0.001, 0.0, True, "ffmpeg"),
            AudioSignal(3.0, 0.002, 0.0, True, "ffmpeg"),
            AudioSignal(5.0, 0.0015, 0.0, True, "ffmpeg"),
            AudioSignal(7.0, 0.001, 0.0, True, "ffmpeg"),
        ]

        self.assertTrue(should_probe_after_selective_skip(low_speech_audio))
        self.assertFalse(should_probe_after_selective_skip(silent_audio))

    def test_analyze_assets_skips_full_transcript_when_probe_finds_no_text(self) -> None:
        asset = Asset(
            id="asset-probe-skip",
            name="Probe Skip",
            source_path="/tmp/probe-skip.mov",
            proxy_path="/tmp/probe-skip.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A012_C001",
        )
        provider = ProbeAwareTranscriptProvider(probe_accepts=False)
        frame_signals = [FrameSignal(2.0, 0.6, 0.6, 0.5, 0.1, 0.3, 0.6, 0.55, "deterministic")]
        audio_signals = [
            AudioSignal(1.0, 0.008, 0.0, False, "ffmpeg"),
            AudioSignal(4.0, 0.01, 0.0, False, "ffmpeg"),
            AudioSignal(8.0, 0.012, 0.0, False, "ffmpeg"),
            AudioSignal(10.0, 0.008, 0.0, False, "ffmpeg"),
        ]

        with unittest.mock.patch(
            "services.analyzer.app.analysis.build_transcript_provider",
            return_value=provider,
        ), unittest.mock.patch(
            "services.analyzer.app.analysis.sample_asset_signals",
            return_value=frame_signals,
        ), unittest.mock.patch(
            "services.analyzer.app.analysis.sample_audio_signals",
            return_value=audio_signals,
        ):
            project = analyze_assets(
                project=ProjectMeta(
                    id="test-project",
                    name="Test Project",
                    story_prompt="Build a rough cut",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 6.0), (6.0, 12.0)]),
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        self.assertEqual(provider.probe_calls, 1)
        self.assertEqual(provider.spans_calls, 0)
        self.assertEqual(project.project.analysis_summary.get("transcript_target_asset_count"), 0)
        self.assertEqual(project.project.analysis_summary.get("transcript_skipped_asset_count"), 1)
        self.assertEqual(project.project.analysis_summary.get("transcript_probed_asset_count"), 1)
        self.assertEqual(project.project.analysis_summary.get("transcript_probe_rejected_asset_count"), 1)

    def test_analyze_assets_runs_full_transcript_when_probe_detects_text(self) -> None:
        asset = Asset(
            id="asset-probe-accept",
            name="Probe Accept",
            source_path="/tmp/probe-accept.mov",
            proxy_path="/tmp/probe-accept.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A013_C001",
        )
        provider = ProbeAwareTranscriptProvider(
            probe_accepts=True,
            spans=[TranscriptSpan(0.5, 4.0, "A useful line lives here.")],
        )
        frame_signals = [FrameSignal(2.0, 0.6, 0.6, 0.5, 0.1, 0.3, 0.6, 0.55, "deterministic")]
        audio_signals = [
            AudioSignal(1.0, 0.008, 0.0, False, "ffmpeg"),
            AudioSignal(4.0, 0.01, 0.0, False, "ffmpeg"),
            AudioSignal(8.0, 0.012, 0.0, False, "ffmpeg"),
            AudioSignal(10.0, 0.008, 0.0, False, "ffmpeg"),
        ]

        with unittest.mock.patch(
            "services.analyzer.app.analysis.build_transcript_provider",
            return_value=provider,
        ), unittest.mock.patch(
            "services.analyzer.app.analysis.sample_asset_signals",
            return_value=frame_signals,
        ), unittest.mock.patch(
            "services.analyzer.app.analysis.sample_audio_signals",
            return_value=audio_signals,
        ):
            project = analyze_assets(
                project=ProjectMeta(
                    id="test-project",
                    name="Test Project",
                    story_prompt="Build a rough cut",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 6.0), (6.0, 12.0)]),
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        self.assertEqual(provider.probe_calls, 1)
        self.assertGreater(provider.spans_calls, 0)
        self.assertEqual(project.project.analysis_summary.get("transcript_target_asset_count"), 1)
        self.assertEqual(project.project.analysis_summary.get("transcript_probed_asset_count"), 1)
        self.assertEqual(project.project.analysis_summary.get("transcript_probe_rejected_asset_count"), 0)
        self.assertTrue(any(segment.transcript_excerpt for segment in project.candidate_segments))

    def test_analyze_assets_counts_speech_fallback_segments_for_speech_test_asset(self) -> None:
        asset = Asset(
            id="asset-007",
            name="IMG_8660",
            source_path="/tmp/img_8660.mov",
            proxy_path="/tmp/img_8660-proxy.mov",
            duration_sec=15.6,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A007_C001",
        )
        frame_signals = [
            FrameSignal(2.0, 0.72, 0.6, 0.5, 0.25, 0.48, 0.72, 0.66, "deterministic"),
            FrameSignal(6.0, 0.74, 0.61, 0.5, 0.26, 0.5, 0.72, 0.68, "deterministic"),
            FrameSignal(10.5, 0.76, 0.62, 0.5, 0.24, 0.52, 0.73, 0.7, "deterministic"),
            FrameSignal(13.0, 0.76, 0.62, 0.5, 0.2, 0.48, 0.73, 0.69, "deterministic"),
        ]
        audio_signals = [
            AudioSignal(2.0, 0.38, 0.5, False, "ffmpeg"),
            AudioSignal(6.0, 0.41, 0.53, False, "ffmpeg"),
            AudioSignal(10.5, 0.45, 0.56, False, "ffmpeg"),
            AudioSignal(13.0, 0.44, 0.55, False, "ffmpeg"),
        ]

        with (
            unittest.mock.patch.dict(
                os.environ,
                {
                    "TIMELINE_TRANSCRIPT_PROVIDER": "disabled",
                    "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "false",
                    "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "false",
                },
                clear=False,
            ),
            unittest.mock.patch("services.analyzer.app.analysis.sample_asset_signals", return_value=frame_signals),
            unittest.mock.patch("services.analyzer.app.analysis.sample_audio_signals", return_value=audio_signals),
        ):
            project = analyze_assets(
                project=ProjectMeta(
                    id="speech-test",
                    name="Speech Test",
                    story_prompt="Keep the strongest spoken beat.",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 5.2), (5.2, 10.4), (10.4, 15.6)]),
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        self.assertGreater(project.project.analysis_summary.get("speech_fallback_segment_count", 0), 0)
        self.assertEqual(project.project.analysis_summary.get("transcript_status"), "disabled")
        self.assertTrue(any(segment.analysis_mode == "speech" for segment in project.candidate_segments))

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
                prefilter=PrefilterDecision(
                    score=0.61,
                    shortlisted=False,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=2,
                    sampled_frame_timestamps_sec=[1.0, 3.0],
                    top_frame_timestamps_sec=[3.0],
                    metrics_snapshot={},
                ),
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
                prefilter=PrefilterDecision(
                    score=0.88,
                    shortlisted=False,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=2,
                    sampled_frame_timestamps_sec=[6.0, 8.0],
                    top_frame_timestamps_sec=[8.0],
                    metrics_snapshot={},
                ),
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
                prefilter=PrefilterDecision(
                    score=0.84,
                    shortlisted=False,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=2,
                    sampled_frame_timestamps_sec=[11.0, 13.0],
                    top_frame_timestamps_sec=[13.0],
                    metrics_snapshot={},
                ),
            ),
        ]

        shortlist_ids = select_prefilter_shortlist_ids(
            asset=asset,
            segments=segments,
            max_segments_per_asset=2,
            mode="fast",
        )
        target_ids = select_ai_target_segment_ids(
            asset=asset,
            segments=segments,
            analyzer=ExpensiveAnalyzerStub(),
            max_segments_per_asset=2,
            mode="fast",
        )

        self.assertEqual(shortlist_ids, target_ids)
        self.assertEqual(len(target_ids), 2)
        self.assertIn("segment-2", target_ids)
        self.assertIn("segment-3", target_ids)

    def test_take_recommendations_include_review_metadata(self) -> None:
        asset = Asset(
            id="asset-review",
            name="Review Clip",
            source_path="/tmp/review.mov",
            proxy_path="/tmp/review-proxy.mov",
            duration_sec=24.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A005_C010",
        )
        segments = [
            CandidateSegment(
                id="seg-best",
                asset_id=asset.id,
                start_sec=0.0,
                end_sec=5.0,
                analysis_mode="speech",
                transcript_excerpt="A clear turning line.",
                description="Winner",
                quality_metrics={
                    "sharpness": 0.8,
                    "stability": 0.78,
                    "visual_novelty": 0.58,
                    "subject_clarity": 0.87,
                    "motion_energy": 0.31,
                    "duration_fit": 0.9,
                    "audio_energy": 0.83,
                    "speech_ratio": 0.94,
                    "hook_strength": 0.92,
                    "story_alignment": 0.95,
                },
            ),
            CandidateSegment(
                id="seg-alt",
                asset_id=asset.id,
                start_sec=5.0,
                end_sec=10.0,
                analysis_mode="speech",
                transcript_excerpt="Useful supporting line.",
                description="Alternate",
                quality_metrics={
                    "sharpness": 0.78,
                    "stability": 0.76,
                    "visual_novelty": 0.52,
                    "subject_clarity": 0.82,
                    "motion_energy": 0.29,
                    "duration_fit": 0.87,
                    "audio_energy": 0.79,
                    "speech_ratio": 0.88,
                    "hook_strength": 0.86,
                    "story_alignment": 0.89,
                },
            ),
            CandidateSegment(
                id="seg-backup",
                asset_id=asset.id,
                start_sec=10.0,
                end_sec=15.0,
                analysis_mode="speech",
                transcript_excerpt="Lower value line.",
                description="Backup",
                quality_metrics={
                    "sharpness": 0.72,
                    "stability": 0.69,
                    "visual_novelty": 0.41,
                    "subject_clarity": 0.71,
                    "motion_energy": 0.23,
                    "duration_fit": 0.78,
                    "audio_energy": 0.51,
                    "speech_ratio": 0.62,
                    "hook_strength": 0.56,
                    "story_alignment": 0.58,
                },
            ),
        ]

        takes = build_take_recommendations([asset], segments)
        take_by_segment_id = {take.candidate_segment_id: take for take in takes}

        self.assertEqual(take_by_segment_id["seg-best"].outcome, "best")
        self.assertEqual(take_by_segment_id["seg-best"].within_asset_rank, 1)
        self.assertEqual(take_by_segment_id["seg-alt"].outcome, "alternate")
        self.assertGreater(take_by_segment_id["seg-alt"].score_gap_to_winner, 0.0)
        self.assertEqual(take_by_segment_id["seg-backup"].outcome, "backup")
        self.assertIn("threshold", take_by_segment_id["seg-backup"].selection_reason)
        self.assertTrue(take_by_segment_id["seg-best"].score_driver_labels)

    def test_segment_review_state_distinguishes_blocked_and_model_paths(self) -> None:
        segment = CandidateSegment(
            id="seg-review-state",
            asset_id="asset-1",
            start_sec=3.0,
            end_sec=8.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Review state segment",
            quality_metrics={"visual_novelty": 0.7},
            prefilter=PrefilterDecision(
                score=0.77,
                shortlisted=True,
                filtered_before_vlm=True,
                selection_reason="Shortlisted but gated.",
                sampled_frame_count=2,
                sampled_frame_timestamps_sec=[4.0, 6.0],
                top_frame_timestamps_sec=[6.0],
                metrics_snapshot={"clip_score": 0.21},
                clip_gated=True,
                vlm_budget_capped=False,
            ),
            evidence_bundle=None,
            ai_understanding=DeterministicVisionLanguageAnalyzer().analyze(
                asset=Asset(
                    id="asset-1",
                    name="Asset One",
                    source_path="/tmp/a.mov",
                    proxy_path="/tmp/a-proxy.mov",
                    duration_sec=10.0,
                    fps=24.0,
                    width=1920,
                    height=1080,
                    has_speech=False,
                    interchange_reel_name="A001_C001",
                ),
                segment=CandidateSegment(
                    id="temp",
                    asset_id="asset-1",
                    start_sec=3.0,
                    end_sec=8.0,
                    analysis_mode="visual",
                    transcript_excerpt="",
                    description="Temp",
                    quality_metrics={"visual_novelty": 0.7},
                ),
                evidence=type(
                    "Evidence",
                    (),
                    {
                        "media_path": "",
                        "transcript_excerpt": "",
                        "story_prompt": "Build a cut",
                        "analysis_mode": "visual",
                        "keyframe_timestamps_sec": [4.0, 6.0],
                        "keyframe_paths": [],
                        "context_window_start_sec": 0.0,
                        "context_window_end_sec": 10.0,
                        "metrics_snapshot": {"visual_novelty": 0.7},
                        "contact_sheet_path": "",
                    },
                )(),
                story_prompt="Build a cut",
            ),
        )

        review_state = build_segment_review_state(segment)

        self.assertTrue(review_state.shortlisted)
        self.assertTrue(review_state.clip_scored)
        self.assertTrue(review_state.clip_gated)
        self.assertTrue(review_state.deterministic_fallback)
        self.assertFalse(review_state.model_analyzed)
        self.assertEqual(review_state.blocked_reason, "clip_gate")
        self.assertIn("CLIP gated", review_state.analysis_path_summary)

    def test_segment_review_state_includes_provenance_summaries(self) -> None:
        segment = CandidateSegment(
            id="seg-provenance",
            asset_id="asset-1",
            start_sec=1.0,
            end_sec=5.0,
            analysis_mode="speech",
            transcript_excerpt="A merged answer.",
            description="Provenance segment",
            quality_metrics={"visual_novelty": 0.7},
            prefilter=PrefilterDecision(
                score=0.81,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="Shortlisted.",
                sampled_frame_count=2,
                sampled_frame_timestamps_sec=[2.0, 4.0],
                top_frame_timestamps_sec=[2.0],
                metrics_snapshot={},
                boundary_strategy="assembly-merge:transcript-continuity",
                boundary_confidence=0.84,
                seed_region_ids=["seed-1", "seed-2"],
                seed_region_sources=["transcript", "transcript"],
                seed_region_ranges_sec=[[1.0, 3.0], [3.2, 5.0]],
                assembly_operation="merge",
                assembly_rule_family="transcript-continuity",
                assembly_source_segment_ids=["asset-1-region-01", "asset-1-region-02"],
                assembly_source_ranges_sec=[[1.0, 3.0], [3.2, 5.0]],
            ),
            boundary_validation=BoundaryValidationResult(
                status="validated",
                decision="keep",
                reason="The merged beat is already complete.",
                confidence=0.81,
                provider="lmstudio",
                provider_model="qwen3.5-9b",
                original_range_sec=[1.0, 5.0],
                suggested_range_sec=[1.0, 5.0],
            ),
        )

        review_state = build_segment_review_state(segment)

        self.assertEqual(review_state.boundary_strategy_label, "Assembly merged (transcript continuity)")
        self.assertEqual(review_state.boundary_confidence, 0.84)
        self.assertIn("Merged 2 refined regions", review_state.lineage_summary)
        self.assertEqual(review_state.semantic_validation_status, "validated")
        self.assertIn("kept the deterministic boundary", review_state.semantic_validation_summary)

    def test_suggested_timeline_duration_preserves_refined_visual_segments(self) -> None:
        scene_segment = CandidateSegment(
            id="seg-scene",
            asset_id="asset-1",
            start_sec=0.0,
            end_sec=6.2,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Scene segment",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=0.7,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[3.0],
                top_frame_timestamps_sec=[3.0],
                metrics_snapshot={},
                boundary_strategy="scene-snap",
                boundary_confidence=0.62,
            ),
        )
        legacy_segment = CandidateSegment(
            id="seg-legacy",
            asset_id="asset-1",
            start_sec=0.0,
            end_sec=6.2,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Legacy segment",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=0.7,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[3.0],
                top_frame_timestamps_sec=[3.0],
                metrics_snapshot={},
                boundary_strategy="legacy",
                boundary_confidence=0.0,
            ),
        )
        merged_segment = CandidateSegment(
            id="seg-merged",
            asset_id="asset-1",
            start_sec=0.0,
            end_sec=6.8,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Merged segment",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=0.7,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[3.0],
                top_frame_timestamps_sec=[3.0],
                metrics_snapshot={},
                boundary_strategy="assembly-merge:structural-continuity",
                boundary_confidence=0.62,
                assembly_operation="merge",
                assembly_rule_family="structural-continuity",
            ),
        )
        speech_segment = CandidateSegment(
            id="seg-speech",
            asset_id="asset-1",
            start_sec=0.0,
            end_sec=8.2,
            analysis_mode="speech",
            transcript_excerpt="A longer line.",
            description="Speech segment",
            quality_metrics={},
        )

        self.assertEqual(suggested_timeline_duration(scene_segment), 6.2)
        self.assertEqual(suggested_timeline_duration(legacy_segment), 5.0)
        self.assertEqual(suggested_timeline_duration(merged_segment), 6.8)
        self.assertEqual(suggested_timeline_duration(speech_segment), 7.5)

    def test_build_timeline_uses_adaptive_trim_for_refined_visual_segments(self) -> None:
        assets = [
            Asset(
                id="asset-1",
                name="Scene Clip",
                source_path="/tmp/scene.mov",
                proxy_path="/tmp/scene.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C130",
            ),
            Asset(
                id="asset-2",
                name="Legacy Clip",
                source_path="/tmp/legacy.mov",
                proxy_path="/tmp/legacy.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C131",
            ),
        ]
        segments = [
            CandidateSegment(
                id="seg-scene",
                asset_id="asset-1",
                start_sec=0.0,
                end_sec=6.2,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Scene segment",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.7,
                    shortlisted=True,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[3.0],
                    top_frame_timestamps_sec=[3.0],
                    metrics_snapshot={},
                    boundary_strategy="scene-snap",
                    boundary_confidence=0.62,
                ),
            ),
            CandidateSegment(
                id="seg-legacy",
                asset_id="asset-2",
                start_sec=0.0,
                end_sec=6.2,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Legacy segment",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.7,
                    shortlisted=True,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[3.0],
                    top_frame_timestamps_sec=[3.0],
                    metrics_snapshot={},
                    boundary_strategy="legacy",
                    boundary_confidence=0.0,
                ),
            ),
        ]
        takes = [
            TakeRecommendation(
                id="take-1",
                candidate_segment_id="seg-scene",
                title="Scene",
                is_best_take=True,
                selection_reason="",
                score_technical=0.3,
                score_semantic=0.3,
                score_story=0.3,
                score_total=0.6,
            ),
            TakeRecommendation(
                id="take-2",
                candidate_segment_id="seg-legacy",
                title="Legacy",
                is_best_take=True,
                selection_reason="",
                score_technical=0.3,
                score_semantic=0.3,
                score_story=0.3,
                score_total=0.5,
            ),
        ]

        timeline = build_timeline(takes, segments, assets)

        self.assertEqual([item.trim_out_sec for item in timeline.items], [6.2, 5.0])

    def test_build_timeline_applies_sequence_heuristics_to_mixed_modes(self) -> None:
        assets = [
            Asset(
                id="asset-1",
                name="Dialogue Clip",
                source_path="/tmp/dialogue.mov",
                proxy_path="/tmp/dialogue.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=True,
                interchange_reel_name="A001_C201",
            ),
            Asset(
                id="asset-2",
                name="Visual Opener",
                source_path="/tmp/opener.mov",
                proxy_path="/tmp/opener.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C202",
            ),
            Asset(
                id="asset-3",
                name="Visual Release",
                source_path="/tmp/release.mov",
                proxy_path="/tmp/release.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C203",
            ),
        ]
        segments = [
            CandidateSegment(
                id="seg-dialogue",
                asset_id="asset-1",
                start_sec=3.0,
                end_sec=8.5,
                analysis_mode="speech",
                transcript_excerpt="The key answer lands here.",
                description="Dialogue beat",
                quality_metrics={"hook_strength": 0.82, "story_alignment": 0.84, "turn_completeness": 0.9},
            ),
            CandidateSegment(
                id="seg-opener",
                asset_id="asset-2",
                start_sec=0.0,
                end_sec=5.8,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Visual opener",
                quality_metrics={"visual_novelty": 0.9, "hook_strength": 0.78, "story_alignment": 0.72, "motion_energy": 0.66},
            ),
            CandidateSegment(
                id="seg-release",
                asset_id="asset-3",
                start_sec=1.0,
                end_sec=6.2,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Visual release",
                quality_metrics={"visual_novelty": 0.71, "hook_strength": 0.74, "story_alignment": 0.75, "motion_energy": 0.31},
            ),
        ]
        takes = [
            TakeRecommendation(
                id="take-dialogue",
                candidate_segment_id="seg-dialogue",
                title="Dialogue",
                is_best_take=True,
                selection_reason="",
                score_technical=0.3,
                score_semantic=0.36,
                score_story=0.34,
                score_total=0.82,
            ),
            TakeRecommendation(
                id="take-opener",
                candidate_segment_id="seg-opener",
                title="Opener",
                is_best_take=True,
                selection_reason="",
                score_technical=0.29,
                score_semantic=0.33,
                score_story=0.31,
                score_total=0.79,
            ),
            TakeRecommendation(
                id="take-release",
                candidate_segment_id="seg-release",
                title="Release",
                is_best_take=True,
                selection_reason="",
                score_technical=0.28,
                score_semantic=0.32,
                score_story=0.3,
                score_total=0.76,
            ),
        ]

        timeline = build_timeline(
            takes,
            segments,
            assets,
            story_prompt="Open on the strongest visual city energy, then land the spoken beat, then end on a calm release.",
        )

        self.assertEqual(
            [item.take_recommendation_id for item in timeline.items],
            ["take-opener", "take-dialogue", "take-release"],
        )
        self.assertEqual([item.sequence_group for item in timeline.items], ["setup", "development", "release"])
        self.assertTrue(any("visual anchor" in reason for reason in timeline.items[0].sequence_rationale))
        self.assertTrue(any("Alternates from visual to speech" in reason for reason in timeline.items[1].sequence_rationale))
        self.assertIn("prompt_fit", timeline.items[0].sequence_driver_labels)
        self.assertIn("repetition_control", timeline.items[1].sequence_driver_labels)

    def test_build_timeline_can_trade_small_local_score_for_prompt_fit(self) -> None:
        assets = [
            Asset(
                id="asset-1",
                name="Speaker",
                source_path="/tmp/speaker.mov",
                proxy_path="/tmp/speaker.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=True,
                interchange_reel_name="A001_C301",
            ),
            Asset(
                id="asset-2",
                name="City Atmosphere",
                source_path="/tmp/city.mov",
                proxy_path="/tmp/city.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C302",
            ),
            Asset(
                id="asset-3",
                name="Quiet Release",
                source_path="/tmp/release.mov",
                proxy_path="/tmp/release.mov",
                duration_sec=12.0,
                fps=24.0,
                width=1920,
                height=1080,
                has_speech=False,
                interchange_reel_name="A001_C303",
            ),
        ]
        segments = [
            CandidateSegment(
                id="seg-speech",
                asset_id="asset-1",
                start_sec=2.0,
                end_sec=7.5,
                analysis_mode="speech",
                transcript_excerpt="The market really begins after this point.",
                description="Confident spoken line from the middle of the scene.",
                quality_metrics={"hook_strength": 0.66, "story_alignment": 0.8, "turn_completeness": 0.9},
            ),
            CandidateSegment(
                id="seg-city",
                asset_id="asset-2",
                start_sec=0.0,
                end_sec=5.6,
                analysis_mode="visual",
                transcript_excerpt="",
                description="City atmosphere with traffic, skyline, and waking street energy.",
                quality_metrics={"visual_novelty": 0.61, "hook_strength": 0.62, "story_alignment": 0.73, "motion_energy": 0.58},
            ),
            CandidateSegment(
                id="seg-release",
                asset_id="asset-3",
                start_sec=1.0,
                end_sec=6.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Calm closing texture with slower movement and softer light.",
                quality_metrics={"visual_novelty": 0.58, "hook_strength": 0.58, "story_alignment": 0.76, "motion_energy": 0.34},
            ),
        ]
        takes = [
            TakeRecommendation(
                id="take-speech",
                candidate_segment_id="seg-speech",
                title="Speech",
                is_best_take=True,
                selection_reason="",
                score_technical=0.31,
                score_semantic=0.35,
                score_story=0.18,
                score_total=0.83,
            ),
            TakeRecommendation(
                id="take-city",
                candidate_segment_id="seg-city",
                title="City",
                is_best_take=True,
                selection_reason="",
                score_technical=0.27,
                score_semantic=0.27,
                score_story=0.18,
                score_total=0.72,
            ),
            TakeRecommendation(
                id="take-release",
                candidate_segment_id="seg-release",
                title="Release",
                is_best_take=True,
                selection_reason="",
                score_technical=0.28,
                score_semantic=0.29,
                score_story=0.19,
                score_total=0.69,
            ),
        ]

        timeline = build_timeline(
            takes,
            segments,
            assets,
            story_prompt="Open on city atmosphere and waking street energy, then move into the spoken market moment, and finish calm.",
        )

        self.assertEqual(
            [item.take_recommendation_id for item in timeline.items],
            ["take-city", "take-speech", "take-release"],
        )
        self.assertIn("prompt_fit", timeline.items[0].sequence_driver_labels)
        self.assertIn("preferred_for_prompt_fit", timeline.items[0].sequence_tradeoff_labels)
        self.assertTrue(any("Matches story prompt cues" in reason for reason in timeline.items[0].sequence_rationale))

    def test_timeline_sequence_metadata_round_trips_through_project_data(self) -> None:
        project = ProjectData(
            project=ProjectMeta(
                id="project-sequence",
                name="Sequence Project",
                story_prompt="Build a sequence",
                status="draft",
                media_roots=["/tmp"],
            ),
            assets=[],
            candidate_segments=[],
            take_recommendations=[],
            timeline=Timeline(
                id="timeline-main",
                version=1,
                story_summary="Visual opener into dialogue then release.",
                items=[
                    TimelineItem(
                        id="timeline-item-01",
                        take_recommendation_id="take-01",
                        order_index=0,
                        trim_in_sec=0.0,
                        trim_out_sec=5.5,
                        label="Opener",
                        notes="Open strong.",
                        source_asset_path="/tmp/a.mov",
                        source_reel="A001_C001",
                        sequence_group="setup",
                        sequence_role="opener",
                        sequence_score=0.84,
                        sequence_rationale=["Starts on a visual anchor.", "Source A001_C001."],
                        sequence_driver_labels=["local_strength", "opener_fit"],
                        sequence_tradeoff_labels=["preferred_for_prompt_fit"],
                    )
                ],
            ),
        )

        restored = ProjectData.from_dict(project.to_dict())
        item = restored.timeline.items[0]
        self.assertEqual(item.sequence_group, "setup")
        self.assertEqual(item.sequence_role, "opener")
        self.assertEqual(item.sequence_rationale, ["Starts on a visual anchor.", "Source A001_C001."])
        self.assertEqual(item.sequence_driver_labels, ["local_strength", "opener_fit"])
        self.assertEqual(item.sequence_tradeoff_labels, ["preferred_for_prompt_fit"])

    def test_load_project_enriches_review_fixture_with_mixed_segment_states(self) -> None:
        project = load_project(REVIEW_FIXTURE)
        segments = {segment.id: segment for segment in project.candidate_segments}
        takes = {take.candidate_segment_id: take for take in project.take_recommendations}

        self.assertEqual(takes["segment-best"].outcome, "best")
        self.assertEqual(takes["segment-alternate"].outcome, "alternate")
        self.assertEqual(takes["segment-clip-gated"].outcome, "backup")
        self.assertEqual(segments["segment-deduped"].review_state.blocked_reason, "duplicate")
        self.assertEqual(segments["segment-budget-capped"].review_state.blocked_reason, "budget_cap")
        self.assertTrue(segments["segment-best"].review_state.model_analyzed)
        self.assertTrue(segments["segment-clip-gated"].review_state.deterministic_fallback)
        self.assertIn("budget capped", segments["segment-budget-capped"].review_state.analysis_path_summary)

    def test_boundary_refinement_uses_transcript_spans_when_enabled(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview.mov",
            duration_sec=20.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C111",
        )
        transcript_provider = TimedTranscriptProvider(
            [
                TranscriptSpan(1.0, 2.5, "How do you start?"),
                TranscriptSpan(2.6, 4.8, "You begin with the strongest frame."),
            ]
        )
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            project = analyze_assets(
                project=ProjectMeta(
                    id="test-project",
                    name="Test Project",
                    story_prompt="Build a rough cut",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 10.0)]),
                transcript_provider=transcript_provider,
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        transcript_segments = [
            segment for segment in project.candidate_segments
            if segment.prefilter and segment.prefilter.boundary_strategy == "turn-snap"
        ]
        self.assertTrue(transcript_segments)
        self.assertTrue(any(segment.start_sec <= 1.0 and segment.end_sec >= 4.8 for segment in transcript_segments))
        self.assertTrue(all(segment.prefilter.seed_region_ids for segment in transcript_segments if segment.prefilter))
        self.assertTrue(all(segment.prefilter.transcript_turn_ids for segment in transcript_segments if segment.prefilter))

    def test_boundary_refinement_uses_audio_when_transcript_missing(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Reaction",
            source_path="/tmp/reaction.mov",
            proxy_path="/tmp/reaction.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C112",
        )
        audio_signals = [
            AudioSignal(timestamp_sec=1.0, rms_energy=0.0, peak_loudness=0.0, is_silent=True, source="ffmpeg"),
            AudioSignal(timestamp_sec=3.0, rms_energy=0.4, peak_loudness=0.5, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=5.0, rms_energy=0.45, peak_loudness=0.6, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=7.0, rms_energy=0.0, peak_loudness=0.0, is_silent=True, source="ffmpeg"),
        ]
        seed_regions = [
            SeedRegion(
                id="seed-1",
                source="audio-peak",
                start_sec=2.5,
                end_sec=5.0,
                score_hint=0.82,
            )
        ]
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.build_prefilter_seed_regions",
                return_value=seed_regions,
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.sample_audio_signals",
                    return_value=audio_signals,
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                        transcript_provider=NoOpTranscriptProvider(),
                        segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                    )

        audio_segments = [
            segment for segment in project.candidate_segments
            if segment.prefilter and segment.prefilter.boundary_strategy == "audio-snap"
        ]
        self.assertTrue(audio_segments)
        self.assertTrue(any(segment.start_sec <= 2.0 and segment.end_sec >= 6.0 for segment in audio_segments))

    def test_boundary_refinement_rejects_audio_snap_when_drift_is_too_large(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Offscreen Audio",
            source_path="/tmp/offscreen.mov",
            proxy_path="/tmp/offscreen.mov",
            duration_sec=14.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C112B",
        )
        audio_signals = [
            AudioSignal(timestamp_sec=1.0, rms_energy=0.0, peak_loudness=0.0, is_silent=True, source="ffmpeg"),
            AudioSignal(timestamp_sec=9.0, rms_energy=0.4, peak_loudness=0.5, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=11.0, rms_energy=0.45, peak_loudness=0.6, is_silent=False, source="ffmpeg"),
            AudioSignal(timestamp_sec=13.0, rms_energy=0.0, peak_loudness=0.0, is_silent=True, source="ffmpeg"),
        ]
        seed_regions = [
            SeedRegion(
                id="seed-1",
                source="audio-peak",
                start_sec=4.5,
                end_sec=7.0,
                score_hint=0.8,
            )
        ]
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.build_prefilter_seed_regions",
                return_value=seed_regions,
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.sample_audio_signals",
                    return_value=audio_signals,
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 14.0)]),
                        transcript_provider=NoOpTranscriptProvider(),
                        segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                    )

        self.assertTrue(project.candidate_segments)
        self.assertTrue(all(segment.prefilter.boundary_strategy != "audio-snap" for segment in project.candidate_segments if segment.prefilter))
        self.assertTrue(any(abs(((segment.start_sec + segment.end_sec) / 2.0) - 5.75) < 1.0 for segment in project.candidate_segments))

    def test_boundary_refinement_falls_back_without_transcript_or_audio(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Silent Visual",
            source_path="/tmp/visual.mov",
            proxy_path="/tmp/visual.mov",
            duration_sec=16.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C113",
        )
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            project = analyze_assets(
                project=ProjectMeta(
                    id="test-project",
                    name="Test Project",
                    story_prompt="Build a rough cut",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 16.0)]),
                transcript_provider=NoOpTranscriptProvider(),
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        self.assertTrue(project.candidate_segments)
        strategies = {
            segment.prefilter.boundary_strategy
            for segment in project.candidate_segments
            if segment.prefilter is not None
        }
        self.assertTrue(strategies.issubset({"scene-duration", "scene-snap", "duration-rule"}))

    def test_boundary_refinement_changes_output_vs_legacy_path(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview.mov",
            duration_sec=20.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C114",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.5, "A complete answer.")])
        legacy_project = ProjectMeta(
            id="test-project-legacy",
            name="Test Project",
            story_prompt="Build a rough cut",
            status="draft",
            media_roots=["/tmp"],
        )
        refined_project = ProjectMeta(
            id="test-project-refined",
            name="Test Project",
            story_prompt="Build a rough cut",
            status="draft",
            media_roots=["/tmp"],
        )
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "false"}, clear=False):
            legacy = analyze_assets(
                project=legacy_project,
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 20.0)]),
                transcript_provider=transcript_provider,
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            refined = analyze_assets(
                project=refined_project,
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 20.0)]),
                transcript_provider=transcript_provider,
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        legacy_ranges = {(segment.start_sec, segment.end_sec) for segment in legacy.candidate_segments}
        refined_ranges = {(segment.start_sec, segment.end_sec) for segment in refined.candidate_segments}
        self.assertNotEqual(legacy_ranges, refined_ranges)
        self.assertTrue(any(segment.prefilter.boundary_strategy != "legacy" for segment in refined.candidate_segments if segment.prefilter))

    def test_boundary_provenance_round_trips_through_project_data(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview.mov",
            duration_sec=20.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C115",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.0, "A complete answer.")])
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            project = analyze_assets(
                project=ProjectMeta(
                    id="test-project",
                    name="Test Project",
                    story_prompt="Build a rough cut",
                    status="draft",
                    media_roots=["/tmp"],
                ),
                assets=[asset],
                scene_detector=StaticSceneDetector([(0.0, 20.0)]),
                transcript_provider=transcript_provider,
                segment_analyzer=DeterministicVisionLanguageAnalyzer(),
            )

        from services.analyzer.app.domain import ProjectData

        restored = ProjectData.from_dict(project.to_dict())
        restored_segment = restored.candidate_segments[0]
        self.assertIsNotNone(restored_segment.prefilter)
        self.assertIn(restored_segment.prefilter.boundary_strategy, {"turn-snap", "transcript-snap", "scene-duration", "scene-snap", "duration-rule"})
        self.assertIsInstance(restored_segment.prefilter.seed_region_ids, list)

    def test_assemble_narrative_units_merges_adjacent_regions_with_transcript_continuity(self) -> None:
        asset = Asset(
            id="asset-merge",
            name="Interview Merge",
            source_path="/tmp/merge.mov",
            proxy_path="/tmp/merge.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C116",
        )
        segments = [
            CandidateSegment(
                id="asset-merge-region-01",
                asset_id=asset.id,
                start_sec=1.0,
                end_sec=3.0,
                analysis_mode="speech",
                transcript_excerpt="How do we start?",
                description="Question",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.8,
                    shortlisted=False,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[2.0],
                    top_frame_timestamps_sec=[2.0],
                    metrics_snapshot={},
                    boundary_strategy="transcript-snap",
                    boundary_confidence=0.9,
                    seed_region_ids=["seed-1"],
                    seed_region_sources=["transcript"],
                    seed_region_ranges_sec=[[1.0, 3.0]],
                    transcript_turn_ids=["turn-01"],
                    transcript_turn_ranges_sec=[[1.0, 5.4]],
                    transcript_turn_alignment="partial-turn",
                ),
            ),
            CandidateSegment(
                id="asset-merge-region-02",
                asset_id=asset.id,
                start_sec=3.2,
                end_sec=5.4,
                analysis_mode="speech",
                transcript_excerpt="We lead with the answer.",
                description="Answer",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.78,
                    shortlisted=False,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[4.0],
                    top_frame_timestamps_sec=[4.0],
                    metrics_snapshot={},
                    boundary_strategy="transcript-snap",
                    boundary_confidence=0.88,
                    seed_region_ids=["seed-2"],
                    seed_region_sources=["transcript"],
                    seed_region_ranges_sec=[[3.2, 5.4]],
                    transcript_turn_ids=["turn-01"],
                    transcript_turn_ranges_sec=[[1.0, 5.4]],
                    transcript_turn_alignment="partial-turn",
                ),
            ),
        ]

        assembled = assemble_narrative_units(
            asset=asset,
            segments=segments,
            base_ranges=[(0.0, 12.0)],
            transcript_spans=[
                TranscriptSpan(1.0, 2.0, "How do we start?"),
                TranscriptSpan(2.1, 3.0, "Start with the strongest moment."),
                TranscriptSpan(3.2, 5.4, "Then carry the answer through."),
            ],
            transcript_turns=derive_transcript_turns(
                [
                    TranscriptSpan(1.0, 2.0, "How do we start?"),
                    TranscriptSpan(2.1, 3.0, "Start with the strongest moment."),
                    TranscriptSpan(3.2, 5.4, "Then carry the answer through."),
                ]
            ),
            transcriber=TimedTranscriptProvider([]),
            prefilter_signals=[],
            audio_signals=[],
        )

        self.assertEqual(len(assembled), 1)
        segment = assembled[0]
        self.assertEqual((segment.start_sec, segment.end_sec), (1.0, 5.4))
        self.assertEqual(segment.prefilter.assembly_operation, "merge")
        self.assertEqual(segment.prefilter.assembly_rule_family, "turn-continuity")
        self.assertEqual(
            segment.prefilter.assembly_source_segment_ids,
            ["asset-merge-region-01", "asset-merge-region-02"],
        )
        self.assertEqual(segment.prefilter.transcript_turn_alignment, "turn-aligned")

    def test_assemble_narrative_units_splits_region_on_transcript_gap(self) -> None:
        asset = Asset(
            id="asset-split",
            name="Interview Split",
            source_path="/tmp/split.mov",
            proxy_path="/tmp/split.mov",
            duration_sec=14.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C117",
        )
        segment = CandidateSegment(
            id="asset-split-region-01",
            asset_id=asset.id,
            start_sec=0.0,
            end_sec=9.0,
            analysis_mode="speech",
            transcript_excerpt="One long region.",
            description="Long region",
            quality_metrics={},
            prefilter=PrefilterDecision(
                score=0.82,
                shortlisted=False,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=1,
                sampled_frame_timestamps_sec=[4.5],
                top_frame_timestamps_sec=[4.5],
                metrics_snapshot={},
                boundary_strategy="transcript-snap",
                boundary_confidence=0.9,
                seed_region_ids=["seed-1"],
                seed_region_sources=["transcript"],
                seed_region_ranges_sec=[[0.0, 9.0]],
            ),
        )

        assembled = assemble_narrative_units(
            asset=asset,
            segments=[segment],
            base_ranges=[(0.0, 14.0)],
            transcript_spans=[
                TranscriptSpan(0.5, 1.5, "Set up."),
                TranscriptSpan(2.0, 3.0, "Explain it."),
                TranscriptSpan(5.5, 6.5, "New idea."),
                TranscriptSpan(7.0, 8.0, "Close it."),
            ],
            transcript_turns=derive_transcript_turns(
                [
                    TranscriptSpan(0.5, 1.5, "Set up."),
                    TranscriptSpan(2.0, 3.0, "Explain it."),
                    TranscriptSpan(5.5, 6.5, "New idea."),
                    TranscriptSpan(7.0, 8.0, "Close it."),
                ]
            ),
            transcriber=TimedTranscriptProvider([]),
            prefilter_signals=[],
            audio_signals=[],
        )

        self.assertEqual(len(assembled), 2)
        self.assertTrue(all(item.prefilter.assembly_operation == "split" for item in assembled))
        self.assertTrue(all(item.prefilter.assembly_rule_family == "turn-break" for item in assembled))
        self.assertTrue(all(item.prefilter.assembly_source_segment_ids == ["asset-split-region-01"] for item in assembled))
        self.assertLessEqual(assembled[0].end_sec, assembled[1].start_sec)

    def test_narrative_assembly_lineage_round_trips_through_project_data(self) -> None:
        project = ProjectData(
            project=ProjectMeta(
                id="project-assembly",
                name="Assembly Project",
                story_prompt="Build a cut",
                status="draft",
                media_roots=["/tmp"],
            ),
            assets=[],
            candidate_segments=[
                CandidateSegment(
                    id="asset-1-segment-01",
                    asset_id="asset-1",
                    start_sec=1.0,
                    end_sec=5.0,
                    analysis_mode="speech",
                    transcript_excerpt="Merged beat.",
                    description="Merged beat",
                    quality_metrics={},
                    prefilter=PrefilterDecision(
                        score=0.8,
                        shortlisted=False,
                        filtered_before_vlm=False,
                        selection_reason="",
                        sampled_frame_count=1,
                        sampled_frame_timestamps_sec=[2.0],
                        top_frame_timestamps_sec=[2.0],
                        metrics_snapshot={},
                        boundary_strategy="assembly-merge:transcript-continuity",
                        boundary_confidence=0.89,
                        assembly_operation="merge",
                        assembly_rule_family="transcript-continuity",
                        assembly_source_segment_ids=["asset-1-region-01", "asset-1-region-02"],
                        assembly_source_ranges_sec=[[1.0, 3.0], [3.2, 5.0]],
                    ),
                )
            ],
            take_recommendations=[],
            timeline=Timeline(id="timeline-main", version=1, story_summary="", items=[]),
        )

        restored = ProjectData.from_dict(project.to_dict())
        prefilter = restored.candidate_segments[0].prefilter
        self.assertIsNotNone(prefilter)
        self.assertEqual(prefilter.assembly_operation, "merge")
        self.assertEqual(prefilter.assembly_rule_family, "transcript-continuity")
        self.assertEqual(prefilter.assembly_source_segment_ids, ["asset-1-region-01", "asset-1-region-02"])

    def test_review_state_provenance_round_trips_through_project_data(self) -> None:
        project = ProjectData(
            project=ProjectMeta(
                id="project-review-provenance",
                name="Review Provenance Project",
                story_prompt="Build a cut",
                status="draft",
                media_roots=["/tmp"],
            ),
            assets=[],
            candidate_segments=[
                CandidateSegment(
                    id="segment-review-provenance",
                    asset_id="asset-1",
                    start_sec=1.0,
                    end_sec=5.0,
                    analysis_mode="speech",
                    transcript_excerpt="A complete beat.",
                    description="Beat",
                    quality_metrics={},
                    review_state=build_segment_review_state(
                        CandidateSegment(
                            id="temp",
                            asset_id="asset-1",
                            start_sec=1.0,
                            end_sec=5.0,
                            analysis_mode="speech",
                            transcript_excerpt="A complete beat.",
                            description="Beat",
                            quality_metrics={},
                            prefilter=PrefilterDecision(
                                score=0.82,
                                shortlisted=True,
                                filtered_before_vlm=False,
                                selection_reason="Shortlisted.",
                                sampled_frame_count=1,
                                sampled_frame_timestamps_sec=[2.0],
                                top_frame_timestamps_sec=[2.0],
                                metrics_snapshot={},
                                boundary_strategy="transcript-snap",
                                boundary_confidence=0.9,
                                seed_region_ids=["seed-1"],
                                seed_region_sources=["transcript"],
                                seed_region_ranges_sec=[[1.0, 5.0]],
                            ),
                            boundary_validation=BoundaryValidationResult(
                                status="skipped",
                                decision="keep",
                                reason="Semantic validation disabled.",
                                confidence=0.0,
                                skip_reason="disabled",
                                original_range_sec=[1.0, 5.0],
                                suggested_range_sec=[1.0, 5.0],
                            ),
                        )
                    ),
                )
            ],
            take_recommendations=[],
            timeline=Timeline(id="timeline-main", version=1, story_summary="", items=[]),
        )

        restored = ProjectData.from_dict(project.to_dict())
        review_state = restored.candidate_segments[0].review_state
        self.assertIsNotNone(review_state)
        self.assertEqual(review_state.boundary_strategy_label, "Transcript snapped")
        self.assertEqual(review_state.semantic_validation_status, "skipped")

    def test_analyze_assets_assembles_speech_heavy_regions_before_scoring(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C118",
        )
        transcript_provider = TimedTranscriptProvider(
            [
                TranscriptSpan(1.0, 2.0, "How do we start?"),
                TranscriptSpan(2.1, 3.0, "Start with the strongest moment."),
                TranscriptSpan(3.2, 5.4, "Then carry the answer through."),
            ]
        )

        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 3.0, "transcript-snap", 0.9, ["seed-1"], ["transcript"], [[1.0, 3.0]]),
                    RefinedSegmentCandidate(3.2, 5.4, "transcript-snap", 0.88, ["seed-2"], ["transcript"], [[3.2, 5.4]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                    transcript_provider=transcript_provider,
                    segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                )

        self.assertEqual(len(project.candidate_segments), 1)
        segment = project.candidate_segments[0]
        self.assertEqual((segment.start_sec, segment.end_sec), (1.0, 5.4))
        self.assertEqual(segment.prefilter.assembly_operation, "merge")
        self.assertEqual(segment.prefilter.assembly_rule_family, "turn-continuity")
        self.assertEqual(segment.prefilter.assembly_source_segment_ids, ["asset-1-region-01", "asset-1-region-02"])
        self.assertEqual(project.take_recommendations[0].candidate_segment_id, segment.id)
        self.assertEqual(project.timeline.items[0].source_asset_path, asset.source_path)

    def test_analyze_assets_assembles_silent_regions_on_structural_continuity(self) -> None:
        asset = Asset(
            id="asset-2",
            name="Silent Action",
            source_path="/tmp/action.mov",
            proxy_path="/tmp/action.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C119",
        )

        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(0.0, 2.0, "scene-snap", 0.62, ["seed-1"], ["scene"], [[0.0, 2.0]]),
                    RefinedSegmentCandidate(2.2, 4.0, "scene-snap", 0.61, ["seed-2"], ["scene"], [[2.2, 4.0]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 10.0)]),
                    transcript_provider=NoOpTranscriptProvider(),
                    segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                )

        self.assertEqual(len(project.candidate_segments), 1)
        self.assertEqual(project.candidate_segments[0].prefilter.assembly_rule_family, "structural-continuity")
        self.assertEqual(project.candidate_segments[0].analysis_mode, "visual")

    def test_analyze_assets_does_not_structurally_merge_overlong_regions(self) -> None:
        asset = Asset(
            id="asset-2b",
            name="Long Silent Action",
            source_path="/tmp/action-long.mov",
            proxy_path="/tmp/action-long.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C119B",
        )

        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(0.0, 5.5, "scene-snap", 0.62, ["seed-1"], ["visual-peak"], [[0.0, 2.5]]),
                    RefinedSegmentCandidate(3.347, 8.847, "scene-snap", 0.61, ["seed-2"], ["visual-peak"], [[4.774, 7.274]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 10.0)]),
                    transcript_provider=NoOpTranscriptProvider(),
                    segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                )

        self.assertGreaterEqual(len(project.candidate_segments), 2)
        self.assertFalse(any(segment.prefilter and segment.prefilter.assembly_operation == "merge" for segment in project.candidate_segments))

    def test_analyze_assets_assembles_mixed_leadin_into_spoken_unit(self) -> None:
        asset = Asset(
            id="asset-3",
            name="Mixed Lead-in",
            source_path="/tmp/mixed.mov",
            proxy_path="/tmp/mixed.mov",
            duration_sec=8.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C120",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(0.95, 2.6, "We start right here.")])

        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(0.0, 0.8, "scene-snap", 0.62, ["seed-1"], ["scene"], [[0.0, 0.8]]),
                    RefinedSegmentCandidate(0.9, 2.6, "turn-snap", 0.9, ["seed-2"], ["transcript"], [[0.9, 2.6]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 8.0)]),
                    transcript_provider=transcript_provider,
                    segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                )

        self.assertEqual(len(project.candidate_segments), 1)
        self.assertEqual(project.candidate_segments[0].analysis_mode, "speech")
        self.assertEqual(project.candidate_segments[0].prefilter.assembly_rule_family, "structural-continuity")

    def test_structural_merge_segments_are_semantically_eligible_at_default_threshold(self) -> None:
        asset = Asset(
            id="asset-3b",
            name="Short Merge",
            source_path="/tmp/short-merge.mov",
            proxy_path="/tmp/short-merge.mov",
            duration_sec=8.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C120B",
        )
        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(0.0, 1.8, "scene-snap", 0.62, ["seed-1"], ["scene"], [[0.0, 1.8]]),
                    RefinedSegmentCandidate(1.9, 3.9, "scene-snap", 0.62, ["seed-2"], ["scene"], [[1.9, 3.9]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    return_value={
                        "asset-3b-segment-01": BoundaryValidationResult(
                            status="validated",
                            decision="keep",
                            reason="Keep the merged beat.",
                            confidence=0.72,
                            provider="lmstudio",
                            provider_model="qwen3.5-9b",
                            original_range_sec=[0.0, 3.9],
                            suggested_range_sec=[0.0, 3.9],
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 8.0)]),
                        transcript_provider=NoOpTranscriptProvider(),
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        segment = project.candidate_segments[0]
        self.assertEqual(segment.prefilter.assembly_rule_family, "structural-continuity")
        self.assertGreaterEqual(semantic_boundary_ambiguity_score(segment), 0.6)
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_eligible_count"), 1)
        self.assertEqual(segment.boundary_validation.status, "validated")

    def test_semantic_boundary_validation_skips_when_disabled(self) -> None:
        asset = Asset(
            id="asset-semantic-disabled",
            name="Ambiguous Interview",
            source_path="/tmp/ambiguous.mov",
            proxy_path="/tmp/ambiguous.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C121",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.5, "This could start tighter.")])

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "false",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 4.5, "duration-rule", 0.42, ["seed-1"], ["peak"], [[1.0, 4.5]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                    transcript_provider=transcript_provider,
                    segment_analyzer=ExpensiveAnalyzerStub(),
                )

        result = project.candidate_segments[0].boundary_validation
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.skip_reason, "disabled")

    def test_semantic_boundary_validation_skips_when_ai_unavailable(self) -> None:
        asset = Asset(
            id="asset-semantic-unavailable",
            name="Ambiguous Interview",
            source_path="/tmp/unavailable.mov",
            proxy_path="/tmp/unavailable.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C122",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.5, "This could start tighter.")])

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 4.5, "duration-rule", 0.42, ["seed-1"], ["peak"], [[1.0, 4.5]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                    transcript_provider=transcript_provider,
                    segment_analyzer=DeterministicVisionLanguageAnalyzer(),
                )

        result = project.candidate_segments[0].boundary_validation
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.skip_reason, "ai_unavailable")

    def test_semantic_boundary_validation_reports_dormant_when_no_segments_cross_threshold(self) -> None:
        asset = Asset(
            id="asset-semantic-dormant",
            name="Stable Interview",
            source_path="/tmp/stable.mov",
            proxy_path="/tmp/stable.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C122B",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.0, "A stable full answer.")])

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
                "TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD": "0.95",
                "TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS": "0",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 4.0, "turn-snap", 0.93, ["seed-1"], ["transcript"], [[1.0, 4.0]]),
                ],
            ):
                project = analyze_assets(
                    project=ProjectMeta(
                        id="test-project",
                        name="Test Project",
                        story_prompt="Build a rough cut",
                        status="draft",
                        media_roots=["/tmp"],
                    ),
                    assets=[asset],
                    scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                    transcript_provider=transcript_provider,
                    segment_analyzer=ExpensiveAnalyzerStub(),
                )

        result = project.candidate_segments[0].boundary_validation
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "not_eligible")
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_dormant"), True)
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_validated_count"), 0)

    def test_semantic_boundary_validation_floor_targets_borderline_segment(self) -> None:
        asset = Asset(
            id="asset-semantic-floor",
            name="Borderline Interview",
            source_path="/tmp/floor.mov",
            proxy_path="/tmp/floor.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C123B",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.0, 4.5, "This is borderline but worth checking.")])

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
                "TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD": "0.8",
                "TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD": "0.45",
                "TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS": "1",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS": "1",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 4.5, "duration-rule", 0.58, ["seed-1"], ["peak"], [[1.0, 4.5]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    return_value={
                        "asset-semantic-floor-segment-01": BoundaryValidationResult(
                            status="validated",
                            decision="keep",
                            reason="Worth checking but keep the current range.",
                            confidence=0.69,
                            provider="lmstudio",
                            provider_model="qwen3.5-9b",
                            original_range_sec=[1.0, 4.5],
                            suggested_range_sec=[1.0, 4.5],
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                        transcript_provider=transcript_provider,
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        result = project.candidate_segments[0].boundary_validation
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "validated")
        self.assertEqual(result.target_reason, "floor")
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_floor_targeted_count"), 1)
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_threshold_targeted_count"), 0)
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_noop_count"), 1)

    def test_semantic_boundary_validation_respects_budget_cap(self) -> None:
        asset = Asset(
            id="asset-semantic-budget",
            name="Budgeted Interview",
            source_path="/tmp/budget.mov",
            proxy_path="/tmp/budget.mov",
            duration_sec=18.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C123",
        )
        transcript_provider = TimedTranscriptProvider(
            [
                TranscriptSpan(1.0, 3.5, "First beat."),
                TranscriptSpan(6.0, 8.5, "Second beat."),
            ]
        )

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS": "1",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT": "100",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 3.5, "duration-rule", 0.41, ["seed-1"], ["peak"], [[1.0, 3.5]]),
                    RefinedSegmentCandidate(6.0, 8.5, "duration-rule", 0.4, ["seed-2"], ["peak"], [[6.0, 8.5]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    side_effect=lambda **kwargs: {
                        kwargs["tasks"][0][0].id: BoundaryValidationResult(
                            status="validated",
                            decision="keep",
                            reason="Keep it.",
                            confidence=0.72,
                            provider="lmstudio",
                            provider_model="qwen3.5-9b",
                            original_range_sec=[kwargs["tasks"][0][0].start_sec, kwargs["tasks"][0][0].end_sec],
                            suggested_range_sec=[kwargs["tasks"][0][0].start_sec, kwargs["tasks"][0][0].end_sec],
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 18.0)]),
                        transcript_provider=transcript_provider,
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        results = [segment.boundary_validation for segment in project.candidate_segments]
        self.assertEqual(sum(1 for result in results if result and result.status == "validated"), 1)
        self.assertEqual(sum(1 for result in results if result and result.skip_reason == "over_budget"), 1)

    def test_semantic_boundary_validation_trims_ambiguous_speech_segment(self) -> None:
        asset = Asset(
            id="asset-semantic-trim",
            name="Trim Interview",
            source_path="/tmp/trim.mov",
            proxy_path="/tmp/trim.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C124",
        )
        transcript_provider = TimedTranscriptProvider([TranscriptSpan(1.2, 4.2, "Use the answer, not the pause.")])

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(0.8, 4.5, "duration-rule", 0.38, ["seed-1"], ["peak"], [[0.8, 4.5]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    return_value={
                        "asset-semantic-trim-segment-01": BoundaryValidationResult(
                            status="validated",
                            decision="trim",
                            reason="The answer starts slightly later.",
                            confidence=0.79,
                            provider="lmstudio",
                            provider_model="qwen3.5-9b",
                            original_range_sec=[0.8, 4.5],
                            suggested_range_sec=[1.3, 4.3],
                            applied=False,
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 10.0)]),
                        transcript_provider=transcript_provider,
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        segment = project.candidate_segments[0]
        self.assertEqual((segment.start_sec, segment.end_sec), (1.3, 4.3))
        self.assertIsNotNone(segment.boundary_validation)
        self.assertEqual(segment.boundary_validation.decision, "trim")
        self.assertTrue(segment.boundary_validation.applied)
        self.assertEqual(project.project.analysis_summary.get("semantic_boundary_applied_count"), 1)

    def test_semantic_boundary_validation_splits_ambiguous_action_segment(self) -> None:
        asset = Asset(
            id="asset-semantic-split",
            name="Action Split",
            source_path="/tmp/action-split.mov",
            proxy_path="/tmp/action-split.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C125",
        )

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 6.0, "assembly-split:scene-divider", 0.39, ["seed-1"], ["peak"], [[1.0, 6.0]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    return_value={
                        "asset-semantic-split-segment-01": BoundaryValidationResult(
                            status="validated",
                            decision="split",
                            reason="This bundles setup and payoff.",
                            confidence=0.83,
                            provider="lmstudio",
                            provider_model="qwen3.5-9b",
                            original_range_sec=[1.0, 6.0],
                            suggested_range_sec=[1.0, 6.0],
                            split_ranges_sec=[[1.0, 3.5], [3.5, 6.0]],
                            applied=False,
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                        transcript_provider=NoOpTranscriptProvider(),
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        self.assertEqual(len(project.candidate_segments), 2)
        self.assertTrue(all(segment.boundary_validation for segment in project.candidate_segments))
        self.assertTrue(all(segment.boundary_validation.decision == "split" for segment in project.candidate_segments))
        self.assertEqual(
            [segment.id for segment in project.candidate_segments],
            ["asset-semantic-split-segment-01", "asset-semantic-split-segment-02"],
        )

    def test_semantic_boundary_validation_ignores_unsupported_scene_split(self) -> None:
        asset = Asset(
            id="asset-semantic-scene-split",
            name="Scene Split",
            source_path="/tmp/scene-split.mov",
            proxy_path="/tmp/scene-split.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C126",
        )

        with unittest.mock.patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
            },
            clear=False,
        ):
            with unittest.mock.patch(
                "services.analyzer.app.analysis.refine_seed_regions",
                return_value=[
                    RefinedSegmentCandidate(1.0, 6.0, "scene-snap", 0.74, ["seed-1"], ["scene"], [[1.0, 6.0]]),
                ],
            ):
                with unittest.mock.patch(
                    "services.analyzer.app.analysis.validate_segment_boundaries",
                    return_value={
                        "asset-semantic-scene-split-segment-01": BoundaryValidationResult(
                            status="validated",
                            decision="split",
                            reason="This looks like two beats.",
                            confidence=0.0,
                            provider="mlx-vlm-local",
                            provider_model="mlx-community/Qwen3.5-0.8B-4bit",
                            original_range_sec=[1.0, 6.0],
                            suggested_range_sec=[1.0, 6.0],
                            split_ranges_sec=[[1.0, 3.5], [3.5, 6.0]],
                            applied=False,
                        )
                    },
                ):
                    project = analyze_assets(
                        project=ProjectMeta(
                            id="test-project",
                            name="Test Project",
                            story_prompt="Build a rough cut",
                            status="draft",
                            media_roots=["/tmp"],
                        ),
                        assets=[asset],
                        scene_detector=StaticSceneDetector([(0.0, 12.0)]),
                        transcript_provider=NoOpTranscriptProvider(),
                        segment_analyzer=ExpensiveAnalyzerStub(),
                    )

        self.assertEqual(len(project.candidate_segments), 1)
        segment = project.candidate_segments[0]
        self.assertEqual((segment.start_sec, segment.end_sec), (1.0, 6.0))
        self.assertIsNotNone(segment.boundary_validation)
        self.assertEqual(segment.boundary_validation.decision, "keep")
        self.assertFalse(segment.boundary_validation.applied)


if __name__ == "__main__":
    unittest.main()
