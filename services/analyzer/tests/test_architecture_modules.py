from __future__ import annotations

import unittest
from dataclasses import replace

from services.analyzer.app import ai, analysis, prefilter, scoring, segmentation, selection, semantic_validation, service, transcripts
from services.analyzer.app.ai_runtime import evidence as ai_evidence
from services.analyzer.app.domain import Asset, CandidateSegment, PrefilterDecision, ProjectData, ProjectMeta, TakeRecommendation, Timeline, TimelineItem
from services.analyzer.app.deduplication import HistogramDeduplicator, deduplicate_segments
from services.analyzer.app.serialization.project_data import project_data_from_dict, project_data_to_dict
from services.analyzer.app.shared import env as shared_env
from services.analyzer.app.shared import numbers as shared_numbers
from services.analyzer.app.shared import strings as shared_strings


class AnalyzerArchitectureModuleTests(unittest.TestCase):
    def test_project_data_serialization_round_trip_matches_domain_helpers(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Clip One",
            source_path="/tmp/source.mov",
            proxy_path="/tmp/proxy.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C001",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id=asset.id,
            start_sec=1.0,
            end_sec=6.0,
            analysis_mode="speech",
            transcript_excerpt="Hello there.",
            description="Opening line.",
            quality_metrics={"story_alignment": 0.8, "turn_completeness": 0.85},
            prefilter=PrefilterDecision(
                score=0.82,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="Shortlisted",
                sampled_frame_count=3,
                sampled_frame_timestamps_sec=[1.5, 3.0, 4.5],
                top_frame_timestamps_sec=[3.0, 4.5],
                metrics_snapshot={"story_alignment": 0.8},
            ),
        )
        take = TakeRecommendation(
            id="take-1",
            candidate_segment_id=segment.id,
            title="Best Dialogue: Clip One",
            is_best_take=True,
            selection_reason="Won this clip at 82/100 on story alignment.",
            score_technical=0.78,
            score_semantic=0.84,
            score_story=0.81,
            score_total=0.82,
            outcome="best",
            within_asset_rank=1,
            score_gap_to_winner=0.0,
            score_driver_labels=["story alignment"],
            limiting_factor_labels=[],
        )
        timeline = Timeline(
            id="timeline-main",
            version=1,
            story_summary="Single selected beat.",
            items=[
                TimelineItem(
                    id="timeline-item-01",
                    take_recommendation_id=take.id,
                    order_index=0,
                    trim_in_sec=0.0,
                    trim_out_sec=5.0,
                    label="Opener",
                    notes="Use first spoken beat.",
                    source_asset_path=asset.source_path,
                    source_reel=asset.interchange_reel_name,
                )
            ],
        )
        project = ProjectData(
            project=ProjectMeta(
                id="project-1",
                name="Project One",
                story_prompt="Build a spoken opener.",
                status="draft",
                media_roots=["/tmp"],
                analysis_summary={"asset_count": 1},
            ),
            assets=[asset],
            candidate_segments=[segment],
            take_recommendations=[take],
            timeline=timeline,
        )

        payload = project.to_dict()

        self.assertEqual(project_data_to_dict(project), payload)
        self.assertEqual(ProjectData.from_dict(payload).to_dict(), payload)
        self.assertEqual(project_data_from_dict(payload).to_dict(), payload)

    def test_shared_helpers_are_reexported_from_compatibility_modules(self) -> None:
        self.assertIs(prefilter.clamp, shared_numbers.clamp)
        self.assertIs(scoring.clamp, shared_numbers.clamp)
        self.assertIs(analysis.clamp, shared_numbers.clamp)
        self.assertIs(prefilter.average, shared_numbers.average)
        self.assertIs(analysis.human_join, shared_strings.human_join)
        self.assertIs(analysis.dedupe_labels, shared_strings.dedupe_labels)
        self.assertIs(analysis.slugify, shared_strings.slugify)
        self.assertIs(ai.parse_bool_env, shared_env.parse_bool_env)
        self.assertIs(ai.parse_int_env, shared_env.parse_int_env)
        self.assertIs(ai.parse_float_env, shared_env.parse_float_env)

    def test_service_module_declares_supported_entrypoints(self) -> None:
        self.assertEqual(
            service.__all__,
            [
                "CLEAR_BEST_TAKE_SENTINEL",
                "apply_best_take_overrides",
                "export_project_fcpxml",
                "export_project_fcpxml_with_override_file",
                "load_project",
                "load_project_with_override_file",
                "read_best_take_overrides",
                "runtime_capabilities",
                "scan_and_analyze_media_root",
            ],
        )

    def test_evidence_module_and_ai_module_share_the_same_builder(self) -> None:
        asset = Asset(
            id="asset-2",
            name="Clip Two",
            source_path="/tmp/source2.mov",
            proxy_path="/tmp/proxy2.mov",
            duration_sec=15.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C002",
        )
        segments = [
            CandidateSegment(
                id="segment-a",
                asset_id=asset.id,
                start_sec=0.0,
                end_sec=5.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="First",
                quality_metrics={"story_alignment": 0.5},
            ),
            CandidateSegment(
                id="segment-b",
                asset_id=asset.id,
                start_sec=5.0,
                end_sec=10.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Second",
                quality_metrics={"story_alignment": 0.7},
            ),
        ]

        evidence_from_facade = ai.build_segment_evidence(
            asset=asset,
            segment=segments[1],
            asset_segments=segments,
            segment_index=1,
            story_prompt="Build a visual bridge.",
            artifacts_root=None,
            extract_keyframes=False,
        )
        evidence_from_module = ai_evidence.build_segment_evidence(
            asset=asset,
            segment=segments[1],
            asset_segments=segments,
            segment_index=1,
            story_prompt="Build a visual bridge.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        self.assertEqual(evidence_from_facade, evidence_from_module)

    def test_transcript_module_and_analysis_module_share_runtime_helpers(self) -> None:
        config = ai.load_ai_analysis_config()

        self.assertIs(analysis.FasterWhisperAdapter, transcripts.FasterWhisperAdapter)
        self.assertIs(analysis.NoOpTranscriptProvider, transcripts.NoOpTranscriptProvider)
        self.assertIs(analysis.build_transcript_provider, transcripts.build_transcript_provider)
        self.assertIs(analysis.derive_transcript_turns, transcripts.derive_transcript_turns)

        provider_from_analysis = analysis.build_transcript_provider(config)
        provider_from_module = transcripts.build_transcript_provider(config)

        self.assertEqual(type(provider_from_analysis), type(provider_from_module))
        self.assertEqual(
            analysis.transcript_runtime_status(provider_from_analysis),
            transcripts.transcript_runtime_status(provider_from_module),
        )

    def test_segmentation_module_and_analysis_module_share_segment_builders(self) -> None:
        asset = Asset(
            id="asset-segmentation",
            name="Segmentation",
            source_path="/tmp/seg-source.mov",
            proxy_path="/tmp/seg-proxy.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C020",
        )
        transcript_spans = [analysis.TranscriptSpan(1.0, 3.0, "How do we start?")]
        transcript_turns = analysis.derive_transcript_turns(transcript_spans)
        prefilter_signals = [
            prefilter.FrameSignal(2.0, 0.8, 0.7, 0.6, 0.4, 0.7, 0.75, 0.82, "ffmpeg"),
        ]
        audio_signals = [
            prefilter.AudioSignal(2.0, 0.08, 0.9, False, "ffmpeg"),
        ]
        transcriber = analysis.NoOpTranscriptProvider()

        segment_from_analysis = analysis.make_candidate_segment(
            asset=asset,
            segment_id="segment-facade",
            start_sec=1.0,
            end_sec=3.0,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            boundary_strategy="turn-snap",
            boundary_confidence=0.93,
            seed_region_ids=["seed-1"],
            seed_region_sources=["transcript"],
            seed_region_ranges_sec=[[1.0, 3.0]],
        )
        segment_from_module = segmentation.make_candidate_segment(
            asset=asset,
            segment_id="segment-facade",
            start_sec=1.0,
            end_sec=3.0,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            boundary_strategy="turn-snap",
            boundary_confidence=0.93,
            seed_region_ids=["seed-1"],
            seed_region_sources=["transcript"],
            seed_region_ranges_sec=[[1.0, 3.0]],
        )

        self.assertEqual(segment_from_analysis, segment_from_module)
        self.assertIs(analysis.RefinedSegmentCandidate, segmentation.RefinedSegmentCandidate)
        self.assertIs(analysis.assemble_narrative_units, segmentation.assemble_narrative_units)
        self.assertIs(analysis.refine_seed_regions, segmentation.refine_seed_regions)

    def test_semantic_validation_module_and_analysis_module_share_boundary_logic(self) -> None:
        segment = CandidateSegment(
            id="segment-semantic",
            asset_id="asset-semantic",
            start_sec=1.0,
            end_sec=4.5,
            analysis_mode="speech",
            transcript_excerpt="A partial answer.",
            description="Semantic candidate.",
            quality_metrics={"turn_completeness": 0.46, "motion_energy": 0.2},
            prefilter=PrefilterDecision(
                score=0.78,
                shortlisted=True,
                filtered_before_vlm=False,
                selection_reason="",
                sampled_frame_count=2,
                sampled_frame_timestamps_sec=[1.5, 3.0],
                top_frame_timestamps_sec=[1.5, 3.0],
                metrics_snapshot={},
                boundary_strategy="duration-rule",
                boundary_confidence=0.41,
                assembly_operation="split",
                assembly_rule_family="turn-break",
                transcript_turn_ids=["turn-01", "turn-02"],
                transcript_turn_alignment="partial-turn",
                seed_region_ranges_sec=[[1.0, 4.5]],
            ),
        )

        self.assertEqual(
            analysis.semantic_boundary_ambiguity_score(segment),
            semantic_validation.semantic_boundary_ambiguity_score(segment),
        )
        self.assertIs(
            analysis.select_semantic_boundary_validation_targets,
            semantic_validation.select_semantic_boundary_validation_targets,
        )
        self.assertIs(
            analysis.apply_semantic_boundary_validation,
            semantic_validation.apply_semantic_boundary_validation,
        )

    def test_selection_modules_and_analysis_module_share_timeline_and_review_logic(self) -> None:
        self.assertIs(analysis.build_take_recommendations, selection.build_take_recommendations)
        self.assertIs(analysis.build_timeline, selection.build_timeline)
        self.assertIs(analysis.build_segment_review_state, selection.build_segment_review_state)
        self.assertIs(analysis.select_ai_target_segment_ids, selection.select_ai_target_segment_ids)
        self.assertIs(analysis.select_prefilter_shortlist_ids, selection.select_prefilter_shortlist_ids)
        self.assertIs(analysis.describe_prefilter_selection, selection.describe_prefilter_selection)
        self.assertIs(analysis.StoryAssemblyChoice, selection.StoryAssemblyChoice)
        self.assertIs(analysis.suggested_timeline_duration, selection.suggested_timeline_duration)

    def test_histogram_deduplication_apis_share_grouping_behavior(self) -> None:
        segments = [
            CandidateSegment(
                id="segment-1",
                asset_id="asset-1",
                start_sec=0.0,
                end_sec=4.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="A",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.9,
                    shortlisted=True,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[1.0],
                    top_frame_timestamps_sec=[1.0],
                    metrics_snapshot={},
                ),
            ),
            CandidateSegment(
                id="segment-2",
                asset_id="asset-1",
                start_sec=4.0,
                end_sec=8.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="B",
                quality_metrics={},
                prefilter=PrefilterDecision(
                    score=0.8,
                    shortlisted=True,
                    filtered_before_vlm=False,
                    selection_reason="",
                    sampled_frame_count=1,
                    sampled_frame_timestamps_sec=[5.0],
                    top_frame_timestamps_sec=[5.0],
                    metrics_snapshot={},
                ),
            ),
        ]
        frame_signals_by_id = {
            "segment-1": [prefilter.FrameSignal(1.0, 0.8, 0.5, 0.4, 0.2, 0.9, 0.6, 0.8, "ffmpeg")],
            "segment-2": [prefilter.FrameSignal(5.0, 0.8, 0.5, 0.4, 0.2, 0.9, 0.6, 0.8, "ffmpeg")],
        }

        direct = deduplicate_segments(
            segments=segments,
            frame_signals_by_id=frame_signals_by_id,
            similarity_threshold=0.85,
        )

        cloned_segments = [
            replace(segment, prefilter=replace(segment.prefilter))
            for segment in segments
        ]
        deduplicator = HistogramDeduplicator(frame_signals_by_id, threshold=0.85)
        deduplicator.deduplicate(cloned_segments)

        self.assertEqual(direct["segment-1"], (False, 0))
        self.assertEqual(direct["segment-2"], (True, 0))
        self.assertTrue(cloned_segments[1].prefilter.deduplicated)
        self.assertEqual(cloned_segments[1].prefilter.dedup_group_id, 0)


if __name__ == "__main__":
    unittest.main()
