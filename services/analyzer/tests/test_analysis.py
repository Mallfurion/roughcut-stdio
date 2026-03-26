from __future__ import annotations

from pathlib import Path
import unittest

from services.analyzer.app.ai import DeterministicVisionLanguageAnalyzer
from services.analyzer.app.analysis import (
    analyze_assets,
    build_segment_review_state,
    build_take_recommendations,
    fallback_segments,
    inspect_runtime_capabilities,
    select_ai_target_segment_ids,
    select_prefilter_shortlist_ids,
)
from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision, ProjectMeta
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


if __name__ == "__main__":
    unittest.main()
