from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.analyzer.app.ai import (
    AIProviderConfig,
    AIProviderRequestError,
    DeterministicVisionLanguageAnalyzer,
    LMStudioVisionLanguageAnalyzer,
    MLXVLMRuntime,
    MLXVLMVisionLanguageAnalyzer,
    boundary_validation_system_prompt,
    boundary_validation_user_prompt,
    build_segment_evidence,
    encode_image_as_data_url,
    inspect_ai_provider_status,
    keyframe_timestamps_for_segment,
    load_ai_analysis_config,
    model_matches,
    normalize_boundary_validation_output,
    normalize_model_output,
    resolve_mlx_device,
    validate_single_segment_boundary,
)
from services.analyzer.app.domain import Asset, CandidateSegment


class AIPhaseOneTests(unittest.TestCase):
    def test_keyframe_timestamps_span_segment(self) -> None:
        timestamps = keyframe_timestamps_for_segment(10.0, 18.0)

        self.assertEqual(len(timestamps), 3)
        self.assertGreater(timestamps[0], 10.0)
        self.assertLess(timestamps[-1], 18.0)

    def test_build_segment_evidence_includes_context_and_metrics(self) -> None:
        asset = Asset(
            id="asset-1",
            name="Crowd Wide",
            source_path="/tmp/crowd.mov",
            proxy_path="/tmp/crowd.mov",
            duration_sec=20.0,
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
                description="First moment.",
                quality_metrics={"visual_novelty": 0.7, "subject_clarity": 0.8, "story_alignment": 0.65},
            ),
            CandidateSegment(
                id="segment-2",
                asset_id="asset-1",
                start_sec=5.0,
                end_sec=10.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Second moment.",
                quality_metrics={"visual_novelty": 0.8, "subject_clarity": 0.7, "story_alignment": 0.72},
            ),
            CandidateSegment(
                id="segment-3",
                asset_id="asset-1",
                start_sec=10.0,
                end_sec=15.0,
                analysis_mode="visual",
                transcript_excerpt="",
                description="Third moment.",
                quality_metrics={"visual_novelty": 0.6, "subject_clarity": 0.75, "story_alignment": 0.68},
            ),
        ]

        evidence = build_segment_evidence(
            asset=asset,
            segment=segments[1],
            asset_segments=segments,
            segment_index=1,
            story_prompt="Build a warm opener.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        self.assertEqual(evidence.context_window_start_sec, 0.0)
        self.assertEqual(evidence.context_window_end_sec, 15.0)
        self.assertEqual(evidence.story_prompt, "Build a warm opener.")
        self.assertEqual(evidence.keyframe_paths, [])

    def test_deterministic_analyzer_returns_structured_output(self) -> None:
        asset = Asset(
            id="asset-2",
            name="Vendor Detail",
            source_path="/tmp/vendor.mov",
            proxy_path="/tmp/vendor.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C002",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-2",
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Vendor Detail provides a transition-ready moment.",
            quality_metrics={
                "visual_novelty": 0.82,
                "subject_clarity": 0.79,
                "story_alignment": 0.76,
                "motion_energy": 0.66,
                "duration_fit": 0.83,
            },
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a textured market sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        understanding = DeterministicVisionLanguageAnalyzer().analyze(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=evidence.story_prompt,
        )

        self.assertEqual(understanding.provider, "deterministic")
        self.assertTrue(understanding.summary)
        self.assertIn(understanding.keep_label, {"keep", "maybe", "reject"})
        self.assertTrue(0.0 <= understanding.confidence <= 1.0)

    def test_normalize_model_output_rejects_placeholder_values(self) -> None:
        asset = Asset(
            id="asset-3",
            name="Field Build",
            source_path="/tmp/field.mov",
            proxy_path="/tmp/field.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C003",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-3",
            start_sec=0.0,
            end_sec=4.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="People build a structure in a field.",
            quality_metrics={
                "visual_novelty": 0.74,
                "subject_clarity": 0.78,
                "story_alignment": 0.71,
                "motion_energy": 0.61,
                "duration_fit": 0.79,
            },
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a practical outdoor sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        understanding = normalize_model_output(
            {
                "summary": "short sentence",
                "subjects": ["short label", "worker"],
                "actions": ["item1", "climbing"],
                "shot_type": "short label",
                "camera_motion": "short label",
                "mood": "short label",
                "keep_label": "short label",
                "confidence": 0.72,
                "rationale": "short sentence",
            },
            provider="mlx-vlm-local",
            model="mlx-community/Qwen3.5-0.8B-4bit",
            fallback=DeterministicVisionLanguageAnalyzer(),
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=evidence.story_prompt,
        )

        self.assertNotEqual(understanding.summary, "short sentence")
        self.assertNotEqual(understanding.shot_type, "short label")
        self.assertNotEqual(understanding.camera_motion, "short label")
        self.assertNotEqual(understanding.mood, "short label")
        self.assertNotEqual(understanding.rationale, "short sentence")
        self.assertNotIn("short label", understanding.subjects)
        self.assertNotIn("item1", understanding.actions)
        self.assertIn(understanding.keep_label, {"keep", "maybe", "reject"})

    def test_boundary_validation_prompt_and_parser_are_structured(self) -> None:
        asset = Asset(
            id="asset-boundary",
            name="Interview",
            source_path="/tmp/interview.mov",
            proxy_path="/tmp/interview.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C900",
        )
        segment = CandidateSegment(
            id="segment-boundary",
            asset_id=asset.id,
            start_sec=1.0,
            end_sec=5.0,
            analysis_mode="speech",
            transcript_excerpt="We start with the answer.",
            description="Interview beat.",
            quality_metrics={"story_alignment": 0.81},
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a concise answer-led cut.",
            artifacts_root=None,
            extract_keyframes=False,
        )

        system_prompt = boundary_validation_system_prompt()
        user_prompt = boundary_validation_user_prompt(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=evidence.story_prompt,
        )
        result = normalize_boundary_validation_output(
            {
                "decision": "trim",
                "reason": "The beat starts a little too early.",
                "confidence": 0.74,
                "suggested_start_sec": 1.4,
                "suggested_end_sec": 4.8,
                "split_point_sec": None,
            },
            provider="lmstudio",
            model="qwen3.5-9b",
            segment=segment,
        )

        self.assertIn("decision", system_prompt)
        self.assertIn("Boundary strategy", user_prompt)
        self.assertEqual(result.status, "validated")
        self.assertEqual(result.decision, "trim")
        self.assertEqual(result.suggested_range_sec, [1.4, 4.8])

    def test_load_ai_analysis_config_reads_semantic_boundary_fields(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION": "true",
                "TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD": "0.82",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT": "40",
                "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS": "3",
                "TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC": "1.8",
            },
            clear=False,
        ):
            config = load_ai_analysis_config()

        self.assertTrue(config.semantic_boundary_validation_enabled)
        self.assertEqual(config.semantic_boundary_ambiguity_threshold, 0.82)
        self.assertEqual(config.semantic_boundary_validation_budget_pct, 40)
        self.assertEqual(config.semantic_boundary_validation_max_segments, 3)
        self.assertEqual(config.semantic_boundary_max_adjustment_sec, 1.8)

    def test_provider_status_defaults_to_deterministic(self) -> None:
        status = inspect_ai_provider_status(
            AIProviderConfig(
                provider="deterministic",
                model="",
                base_url="http://127.0.0.1:1234/v1",
                timeout_sec=30.0,
            )
        )

        self.assertEqual(status.effective_provider, "deterministic")
        self.assertTrue(status.available)

    def test_provider_status_reports_missing_mlx_vlm_dependencies(self) -> None:
        with patch("services.analyzer.app.ai.missing_mlx_vlm_dependencies", return_value=["mlx", "mlx-vlm", "torch", "torchvision"]):
            status = inspect_ai_provider_status(
                AIProviderConfig(
                    provider="mlx-vlm-local",
                    model="mlx-community/Qwen3.5-0.8B-4bit",
                    base_url="",
                    timeout_sec=30.0,
                    cache_dir="/tmp/mlx-vlm",
                    device="auto",
                )
            )

        self.assertEqual(status.configured_provider, "mlx-vlm-local")
        self.assertEqual(status.effective_provider, "deterministic")
        self.assertFalse(status.available)
        self.assertIn("missing", status.detail.lower())
        self.assertIn("torch", status.detail.lower())

    def test_provider_status_reports_missing_ffmpeg_for_mlx_vlm(self) -> None:
        with (
            patch("services.analyzer.app.ai.missing_mlx_vlm_dependencies", return_value=[]),
            patch("services.analyzer.app.ai.platform.system", return_value="Darwin"),
            patch("services.analyzer.app.ai.platform.machine", return_value="arm64"),
            patch("services.analyzer.app.ai.shutil.which", return_value=None),
        ):
            status = inspect_ai_provider_status(
                AIProviderConfig(
                    provider="mlx-vlm-local",
                    model="mlx-community/Qwen3.5-0.8B-4bit",
                    base_url="",
                    timeout_sec=30.0,
                    cache_dir="/tmp/mlx-vlm",
                    device="auto",
                )
            )

        self.assertEqual(status.configured_provider, "mlx-vlm-local")
        self.assertEqual(status.effective_provider, "deterministic")
        self.assertFalse(status.available)
        self.assertIn("ffmpeg", status.detail.lower())

    def test_provider_status_requires_prepared_local_mlx_model(self) -> None:
        with (
            patch("services.analyzer.app.ai.missing_mlx_vlm_dependencies", return_value=[]),
            patch("services.analyzer.app.ai.platform.system", return_value="Darwin"),
            patch("services.analyzer.app.ai.platform.machine", return_value="arm64"),
            patch("services.analyzer.app.ai.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
            patch("services.analyzer.app.ai.resolve_prepared_mlx_vlm_model_path", return_value=None),
        ):
            status = inspect_ai_provider_status(
                AIProviderConfig(
                    provider="mlx-vlm-local",
                    model="mlx-community/Qwen3.5-0.8B-4bit",
                    base_url="",
                    timeout_sec=30.0,
                    cache_dir="/tmp/mlx-vlm",
                    device="auto",
                )
            )

        self.assertEqual(status.configured_provider, "mlx-vlm-local")
        self.assertEqual(status.effective_provider, "deterministic")
        self.assertFalse(status.available)
        self.assertIn("setup", status.detail.lower())

    def test_model_matches_handles_aliases(self) -> None:
        self.assertTrue(model_matches("qwen3.5-9b", "lmstudio-community/qwen3.5-9b"))
        self.assertTrue(model_matches("lmstudio-community/qwen3.5-9b", "qwen3.5-9b"))
        self.assertFalse(model_matches("qwen3.5-9b", "gemma-3-12b"))

    def test_encode_image_as_data_url_ignores_empty_or_directory_paths(self) -> None:
        self.assertIsNone(encode_image_as_data_url(""))
        self.assertIsNone(encode_image_as_data_url("."))

    def test_resolve_mlx_device_defaults_to_metal(self) -> None:
        self.assertEqual(resolve_mlx_device(requested="auto"), "metal")
        self.assertEqual(resolve_mlx_device(requested="mps"), "metal")
        self.assertEqual(resolve_mlx_device(requested="cpu"), "cpu")

    def test_lmstudio_analyzer_stores_and_reuses_cache(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def create_json_completion(self, *, model: str, system_prompt: str, user_prompt: str, image_paths, timeout_sec: float):
                self.calls += 1
                return {
                    "summary": "Strong visual moment.",
                    "subjects": ["crowd"],
                    "actions": ["moving"],
                    "shot_type": "wide",
                    "camera_motion": "gentle movement",
                    "mood": "energetic",
                    "story_roles": ["bridge"],
                    "quality_findings": ["usable motion"],
                    "keep_label": "keep",
                    "confidence": 0.88,
                    "rationale": "Useful coverage.",
                    "risk_flags": [],
                    "visual_distinctiveness": 0.81,
                    "clarity": 0.77,
                    "story_relevance": 0.74,
                }

        asset = Asset(
            id="asset-2",
            name="Vendor Detail",
            source_path="/tmp/vendor.mov",
            proxy_path="/tmp/vendor.mov",
            duration_sec=12.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C002",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-2",
            start_sec=0.0,
            end_sec=5.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Vendor Detail provides a transition-ready moment.",
            quality_metrics={
                "visual_novelty": 0.82,
                "subject_clarity": 0.79,
                "story_alignment": 0.76,
                "motion_energy": 0.66,
                "duration_fit": 0.83,
            },
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a textured market sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )
        client = FakeClient()

        with tempfile.TemporaryDirectory() as tempdir:
            analyzer = LMStudioVisionLanguageAnalyzer(
                config=AIProviderConfig(
                    provider="lmstudio",
                    model="qwen3.5-9b",
                    base_url="http://127.0.0.1:1234/v1",
                    timeout_sec=30.0,
                ),
                client=client,
                cache_root=Path(tempdir),
            )

            first = analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=evidence.story_prompt,
            )
            second = analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=evidence.story_prompt,
            )
            stats = analyzer.runtime_stats()

        self.assertEqual(client.calls, 1)
        self.assertEqual(first.summary, second.summary)
        self.assertEqual(stats.live_segment_count, 1)
        self.assertEqual(stats.cached_segment_count, 1)
        self.assertEqual(stats.fallback_segment_count, 0)
        self.assertEqual(stats.live_request_count, 1)

    def test_lmstudio_analyzer_batches_asset_segments(self) -> None:
        class FakeBatchClient:
            def __init__(self) -> None:
                self.calls = 0

            def create_json_completion(self, *, model: str, system_prompt: str, user_prompt: str, image_paths, timeout_sec: float):
                self.calls += 1
                return {
                    "segments": [
                        {
                            "segment_id": "segment-1",
                            "summary": "First strong moment.",
                            "subjects": ["crowd"],
                            "actions": ["moving"],
                            "shot_type": "wide",
                            "camera_motion": "gentle movement",
                            "mood": "energetic",
                            "story_roles": ["bridge"],
                            "quality_findings": ["usable motion"],
                            "keep_label": "keep",
                            "confidence": 0.81,
                            "rationale": "Useful first beat.",
                            "risk_flags": [],
                            "visual_distinctiveness": 0.8,
                            "clarity": 0.76,
                            "story_relevance": 0.72,
                        },
                        {
                            "segment_id": "segment-2",
                            "summary": "Second strong moment.",
                            "subjects": ["subject"],
                            "actions": ["walking"],
                            "shot_type": "medium",
                            "camera_motion": "active movement",
                            "mood": "cinematic",
                            "story_roles": ["payoff"],
                            "quality_findings": ["clear framing"],
                            "keep_label": "keep",
                            "confidence": 0.84,
                            "rationale": "Useful second beat.",
                            "risk_flags": [],
                            "visual_distinctiveness": 0.83,
                            "clarity": 0.79,
                            "story_relevance": 0.75,
                        },
                    ]
                }

        asset = Asset(
            id="asset-3",
            name="Crowd Walk",
            source_path="/tmp/crowd.mov",
            proxy_path="/tmp/crowd.mov",
            duration_sec=16.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A001_C003",
        )
        segment_one = CandidateSegment(
            id="segment-1",
            asset_id="asset-3",
            start_sec=0.0,
            end_sec=4.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="First",
            quality_metrics={"visual_novelty": 0.78, "subject_clarity": 0.74, "story_alignment": 0.7, "motion_energy": 0.62, "duration_fit": 0.81},
        )
        segment_two = CandidateSegment(
            id="segment-2",
            asset_id="asset-3",
            start_sec=4.0,
            end_sec=8.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Second",
            quality_metrics={"visual_novelty": 0.81, "subject_clarity": 0.78, "story_alignment": 0.73, "motion_energy": 0.68, "duration_fit": 0.82},
        )
        evidence_one = build_segment_evidence(
            asset=asset,
            segment=segment_one,
            asset_segments=[segment_one, segment_two],
            segment_index=0,
            story_prompt="Build a rhythmic sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )
        evidence_two = build_segment_evidence(
            asset=asset,
            segment=segment_two,
            asset_segments=[segment_one, segment_two],
            segment_index=1,
            story_prompt="Build a rhythmic sequence.",
            artifacts_root=None,
            extract_keyframes=False,
        )
        client = FakeBatchClient()

        with tempfile.TemporaryDirectory() as tempdir:
            analyzer = LMStudioVisionLanguageAnalyzer(
                config=AIProviderConfig(
                    provider="lmstudio",
                    model="qwen3.5-9b",
                    base_url="http://127.0.0.1:1234/v1",
                    timeout_sec=30.0,
                ),
                client=client,
                cache_root=Path(tempdir),
            )

            results = analyzer.analyze_asset_segments(
                asset=asset,
                tasks=[
                    (segment_one, evidence_one, evidence_one.story_prompt),
                    (segment_two, evidence_two, evidence_two.story_prompt),
                ],
            )
            stats = analyzer.runtime_stats()

        self.assertEqual(client.calls, 1)
        self.assertEqual(set(results.keys()), {"segment-1", "segment-2"})
        self.assertEqual(results["segment-1"].provider, "lmstudio")
        self.assertEqual(results["segment-2"].provider, "lmstudio")
        self.assertEqual(stats.live_segment_count, 2)
        self.assertEqual(stats.cached_segment_count, 0)
        self.assertEqual(stats.fallback_segment_count, 0)
        self.assertEqual(stats.live_request_count, 1)

    def test_validate_single_segment_boundary_falls_back_on_lmstudio_error(self) -> None:
        class FailingClient:
            def create_json_completion(self, *, model: str, system_prompt: str, user_prompt: str, image_paths, timeout_sec: float):
                raise AIProviderRequestError("boom")

        asset = Asset(
            id="asset-boundary-fallback",
            name="Boundary Fallback",
            source_path="/tmp/boundary.mov",
            proxy_path="/tmp/boundary.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=True,
            interchange_reel_name="A001_C901",
        )
        segment = CandidateSegment(
            id="segment-boundary-fallback",
            asset_id=asset.id,
            start_sec=1.0,
            end_sec=4.0,
            analysis_mode="speech",
            transcript_excerpt="Start here.",
            description="Boundary fallback.",
            quality_metrics={"story_alignment": 0.77},
        )
        evidence = build_segment_evidence(
            asset=asset,
            segment=segment,
            asset_segments=[segment],
            segment_index=0,
            story_prompt="Build a rough cut.",
            artifacts_root=None,
            extract_keyframes=False,
        )
        analyzer = LMStudioVisionLanguageAnalyzer(
            config=AIProviderConfig(
                provider="lmstudio",
                model="qwen3.5-9b",
                base_url="http://127.0.0.1:1234/v1",
                timeout_sec=30.0,
            ),
            client=FailingClient(),
        )

        result = validate_single_segment_boundary(
            analyzer=analyzer,
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=evidence.story_prompt,
        )

        self.assertEqual(result.status, "fallback")
        self.assertEqual(result.decision, "keep")
        self.assertEqual(result.skip_reason, "request_failed")

    def test_mlx_vlm_local_analyzer_uses_runtime_and_cache(self) -> None:
        class FakeRuntime:
            def __init__(self) -> None:
                self.model_id = "mlx-community/Qwen3.5-0.8B-4bit"
                self.revision = ""
                self.device = "metal"
                self.cache_dir = "/tmp/mlx-vlm"
                self.calls = 0

            def query_image(self, *, image_path: str, prompt: str) -> str:
                self.calls += 1
                return """
                {
                  "summary": "A useful bridge shot.",
                  "subjects": ["crowd"],
                  "actions": ["moving"],
                  "shot_type": "wide",
                  "camera_motion": "gentle movement",
                  "mood": "energetic",
                  "story_roles": ["bridge"],
                  "quality_findings": ["usable motion"],
                  "keep_label": "keep",
                  "confidence": 0.86,
                  "rationale": "Good motion and readable subject.",
                  "risk_flags": [],
                  "visual_distinctiveness": 0.8,
                  "clarity": 0.78,
                  "story_relevance": 0.74
                }
                """

        asset = Asset(
            id="asset-4",
            name="Bridge Shot",
            source_path="/tmp/bridge.mov",
            proxy_path="/tmp/bridge.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A004_C021",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-4",
            start_sec=0.0,
            end_sec=4.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Bridge shot.",
            quality_metrics={"visual_novelty": 0.8, "subject_clarity": 0.79, "story_alignment": 0.73, "motion_energy": 0.66, "duration_fit": 0.8},
        )
        with tempfile.TemporaryDirectory() as tempdir:
            image_path = Path(tempdir) / "segment.jpg"
            image_path.write_bytes(b"fake")
            evidence = build_segment_evidence(
                asset=asset,
                segment=segment,
                asset_segments=[segment],
                segment_index=0,
                story_prompt="Build a rough cut.",
                artifacts_root=None,
                extract_keyframes=False,
            )
            evidence.contact_sheet_path = str(image_path)
            runtime = FakeRuntime()
            analyzer = MLXVLMVisionLanguageAnalyzer(
                config=AIProviderConfig(
                    provider="mlx-vlm-local",
                    model="mlx-community/Qwen3.5-0.8B-4bit",
                    base_url="",
                    timeout_sec=30.0,
                    revision="",
                    cache_dir=tempdir,
                    device="auto",
                ),
                runtime=runtime,
                cache_root=Path(tempdir) / "cache",
            )

            first = analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=evidence.story_prompt,
            )
            second = analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=evidence.story_prompt,
            )
            stats = analyzer.runtime_stats()

        self.assertEqual(runtime.calls, 1)
        self.assertEqual(first.provider, "mlx-vlm-local")
        self.assertEqual(second.provider, "mlx-vlm-local")
        self.assertEqual(stats.live_segment_count, 1)
        self.assertEqual(stats.cached_segment_count, 1)
        self.assertEqual(stats.fallback_segment_count, 0)
        self.assertEqual(stats.live_request_count, 1)

    def test_mlx_vlm_local_analyzer_falls_back_on_runtime_error(self) -> None:
        class FailingRuntime:
            def __init__(self) -> None:
                self.model_id = "mlx-community/Qwen3.5-0.8B-4bit"
                self.revision = ""
                self.device = "metal"
                self.cache_dir = "/tmp/mlx-vlm"

            def query_image(self, *, image_path: str, prompt: str) -> str:
                raise RuntimeError("mlx runtime failure")

        asset = Asset(
            id="asset-5",
            name="Fallback Shot",
            source_path="/tmp/fallback.mov",
            proxy_path="/tmp/fallback.mov",
            duration_sec=10.0,
            fps=24.0,
            width=1920,
            height=1080,
            has_speech=False,
            interchange_reel_name="A005_C031",
        )
        segment = CandidateSegment(
            id="segment-1",
            asset_id="asset-5",
            start_sec=0.0,
            end_sec=4.0,
            analysis_mode="visual",
            transcript_excerpt="",
            description="Fallback shot.",
            quality_metrics={"visual_novelty": 0.8, "subject_clarity": 0.79, "story_alignment": 0.73, "motion_energy": 0.66, "duration_fit": 0.8},
        )
        with tempfile.TemporaryDirectory() as tempdir:
            image_path = Path(tempdir) / "segment.jpg"
            image_path.write_bytes(b"fake")
            evidence = build_segment_evidence(
                asset=asset,
                segment=segment,
                asset_segments=[segment],
                segment_index=0,
                story_prompt="Build a rough cut.",
                artifacts_root=None,
                extract_keyframes=False,
            )
            evidence.contact_sheet_path = str(image_path)
            analyzer = MLXVLMVisionLanguageAnalyzer(
                config=AIProviderConfig(
                    provider="mlx-vlm-local",
                    model="mlx-community/Qwen3.5-0.8B-4bit",
                    base_url="",
                    timeout_sec=30.0,
                    revision="",
                    cache_dir=tempdir,
                    device="auto",
                ),
                runtime=FailingRuntime(),
                cache_root=Path(tempdir) / "cache",
            )

            understanding = analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=evidence.story_prompt,
            )
            stats = analyzer.runtime_stats()

        self.assertEqual(understanding.provider, "deterministic")
        self.assertIn("mlx_vlm_local_failed", understanding.risk_flags)
        self.assertEqual(stats.live_segment_count, 0)
        self.assertEqual(stats.cached_segment_count, 0)
        self.assertEqual(stats.fallback_segment_count, 1)
        self.assertEqual(stats.live_request_count, 1)

    def test_mlx_vlm_runtime_uses_prepared_inputs_for_qwen3_models(self) -> None:
        class FakeArray(list):
            def __init__(self, value):
                if isinstance(value, FakeArray):
                    super().__init__(value)
                elif isinstance(value, list):
                    super().__init__(value)
                else:
                    super().__init__([value])

        class FakeProcessor:
            def __init__(self) -> None:
                self.calls = 0

            def apply_chat_template(self, messages, **kwargs):
                self.calls += 1
                self.last_messages = messages
                self.last_kwargs = kwargs
                return {
                    "input_ids": [[1, 2, 3]],
                    "attention_mask": [[1, 1, 1]],
                    "pixel_values": [[0.1, 0.2, 0.3]],
                    "image_grid_thw": [[1, 1, 1]],
                }

        class FakeGenerateModule:
            def __init__(self) -> None:
                self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def generate(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return '{"summary":"ok"}'

        fake_processor = FakeProcessor()
        fake_generate_module = FakeGenerateModule()
        fake_mx = SimpleNamespace(array=FakeArray)
        runtime = MLXVLMRuntime(
            model_id="mlx-community/Qwen3.5-0.8B-4bit",
            revision="",
            cache_dir="/tmp/mlx-vlm",
            device="metal",
        )
        runtime._model = object()
        runtime._processor = fake_processor
        runtime._config = {"model_type": "qwen3_5"}

        def fake_import_module(name: str):
            if name == "mlx.core":
                return fake_mx
            if name == "mlx_vlm":
                return SimpleNamespace(generate=fake_generate_module.generate)
            raise AssertionError(f"Unexpected import: {name}")

        with tempfile.TemporaryDirectory() as tempdir:
            image_path = Path(tempdir) / "segment.jpg"
            image_path.write_bytes(b"fake")
            with patch("services.analyzer.app.ai.importlib.import_module", side_effect=fake_import_module):
                result = runtime.query_image(image_path=str(image_path), prompt="Describe this segment.")

        self.assertEqual(result, '{"summary":"ok"}')
        self.assertEqual(fake_processor.calls, 1)
        self.assertEqual(len(fake_generate_module.calls), 1)
        args, kwargs = fake_generate_module.calls[0]
        self.assertEqual(args[0], runtime._model)
        self.assertEqual(args[1], fake_processor)
        self.assertEqual(args[2], "")
        self.assertIn("input_ids", kwargs)
        self.assertIn("pixel_values", kwargs)
        self.assertIn("mask", kwargs)
        self.assertIn("image_grid_thw", kwargs)
        self.assertEqual(
            fake_processor.last_messages[0]["content"][0]["image"],
            str(image_path),
        )
        self.assertEqual(fake_processor.last_kwargs["return_tensors"], "pt")


if __name__ == "__main__":
    unittest.main()
