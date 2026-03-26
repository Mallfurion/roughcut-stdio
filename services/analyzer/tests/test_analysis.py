from __future__ import annotations

import os
from pathlib import Path
import unittest
import unittest.mock

from services.analyzer.app.ai import DeterministicVisionLanguageAnalyzer
from services.analyzer.app.analysis import (
    NoOpTranscriptProvider,
    RefinedSegmentCandidate,
    TranscriptSpan,
    analyze_assets,
    assemble_narrative_units,
    build_segment_review_state,
    build_take_recommendations,
    fallback_segments,
    inspect_runtime_capabilities,
    select_ai_target_segment_ids,
    select_prefilter_shortlist_ids,
)
from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision, ProjectData, ProjectMeta, Timeline
from services.analyzer.app.prefilter import AudioSignal
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
            if segment.prefilter and segment.prefilter.boundary_strategy == "transcript-snap"
        ]
        self.assertTrue(transcript_segments)
        self.assertTrue(any(segment.start_sec <= 1.0 and segment.end_sec >= 4.8 for segment in transcript_segments))
        self.assertTrue(all(segment.prefilter.seed_region_ids for segment in transcript_segments if segment.prefilter))

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
        with unittest.mock.patch.dict(os.environ, {"TIMELINE_SEGMENT_BOUNDARY_REFINEMENT": "true"}, clear=False):
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
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
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
        self.assertIn(restored_segment.prefilter.boundary_strategy, {"transcript-snap", "scene-duration", "scene-snap", "duration-rule"})
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
            transcriber=TimedTranscriptProvider([]),
            prefilter_signals=[],
            audio_signals=[],
        )

        self.assertEqual(len(assembled), 1)
        segment = assembled[0]
        self.assertEqual((segment.start_sec, segment.end_sec), (1.0, 5.4))
        self.assertEqual(segment.prefilter.assembly_operation, "merge")
        self.assertEqual(segment.prefilter.assembly_rule_family, "transcript-continuity")
        self.assertEqual(
            segment.prefilter.assembly_source_segment_ids,
            ["asset-merge-region-01", "asset-merge-region-02"],
        )

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
            transcriber=TimedTranscriptProvider([]),
            prefilter_signals=[],
            audio_signals=[],
        )

        self.assertEqual(len(assembled), 2)
        self.assertTrue(all(item.prefilter.assembly_operation == "split" for item in assembled))
        self.assertTrue(all(item.prefilter.assembly_rule_family == "transcript-gap" for item in assembled))
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
                    RefinedSegmentCandidate(0.9, 2.6, "transcript-snap", 0.9, ["seed-2"], ["transcript"], [[0.9, 2.6]]),
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


if __name__ == "__main__":
    unittest.main()
