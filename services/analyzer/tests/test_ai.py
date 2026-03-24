from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.analyzer.app.ai import (
    AIProviderConfig,
    DeterministicVisionLanguageAnalyzer,
    LMStudioVisionLanguageAnalyzer,
    MoondreamLocalVisionLanguageAnalyzer,
    build_segment_evidence,
    encode_image_as_data_url,
    inspect_ai_provider_status,
    keyframe_timestamps_for_segment,
    model_matches,
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

    def test_provider_status_reports_missing_moondream_dependencies(self) -> None:
        with patch("services.analyzer.app.ai.missing_moondream_dependencies", return_value=["torch", "transformers"]):
            status = inspect_ai_provider_status(
                AIProviderConfig(
                    provider="moondream-local",
                    model="vikhyatk/moondream2",
                    base_url="",
                    timeout_sec=30.0,
                    cache_dir="/tmp/moondream",
                    device="auto",
                )
            )

        self.assertEqual(status.configured_provider, "moondream-local")
        self.assertEqual(status.effective_provider, "deterministic")
        self.assertFalse(status.available)
        self.assertIn("missing", status.detail.lower())

    def test_model_matches_handles_aliases(self) -> None:
        self.assertTrue(model_matches("qwen3.5-9b", "lmstudio-community/qwen3.5-9b"))
        self.assertTrue(model_matches("lmstudio-community/qwen3.5-9b", "qwen3.5-9b"))
        self.assertFalse(model_matches("qwen3.5-9b", "gemma-3-12b"))

    def test_encode_image_as_data_url_ignores_empty_or_directory_paths(self) -> None:
        self.assertIsNone(encode_image_as_data_url(""))
        self.assertIsNone(encode_image_as_data_url("."))

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
                    model="moondream-2b-2025-04-14",
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

    def test_moondream_local_analyzer_uses_runtime_and_cache(self) -> None:
        class FakeRuntime:
            def __init__(self) -> None:
                self.model_id = "vikhyatk/moondream2"
                self.revision = "2025-04-14"
                self.device = "cpu"
                self.cache_dir = "/tmp/moondream"
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
            analyzer = MoondreamLocalVisionLanguageAnalyzer(
                config=AIProviderConfig(
                    provider="moondream-local",
                    model="vikhyatk/moondream2",
                    base_url="",
                    timeout_sec=30.0,
                    revision="2025-04-14",
                    cache_dir=tempdir,
                    device="cpu",
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
        self.assertEqual(first.provider, "moondream-local")
        self.assertEqual(second.provider, "moondream-local")
        self.assertEqual(stats.live_segment_count, 1)
        self.assertEqual(stats.cached_segment_count, 1)
        self.assertEqual(stats.fallback_segment_count, 0)
        self.assertEqual(stats.live_request_count, 1)


if __name__ == "__main__":
    unittest.main()
