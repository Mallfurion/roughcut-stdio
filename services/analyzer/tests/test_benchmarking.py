from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.analyzer.app.benchmarking import (
    attach_quality_evaluation,
    build_process_benchmark,
    build_process_summary_lines,
    compare_benchmarks,
    load_previous_matching_benchmark_entry,
    write_benchmark_artifacts,
    write_process_log,
)


class ProcessBenchmarkingTests(unittest.TestCase):
    def test_benchmark_artifacts_include_process_output_paths(self) -> None:
        payload = {
            "project": {
                "analysis_summary": {
                    "phase_timings_sec": {
                        "media_discovery": 1.25,
                        "per_asset_analysis": 9.5,
                        "take_selection": 0.33,
                        "timeline_assembly": 0.12,
                    },
                    "prefilter_sample_count": 16,
                    "deterministic_preprocessing_cache_hit_asset_count": 1,
                    "deterministic_preprocessing_cache_rebuilt_asset_count": 0,
                    "candidate_segment_count": 4,
                    "prefilter_shortlisted_count": 2,
                    "vlm_target_count": 1,
                    "filtered_before_vlm_count": 1,
                    "audio_signal_asset_count": 1,
                    "audio_silent_asset_count": 0,
                    "transcript_status": "partial-fallback",
                    "transcript_provider_effective": "faster-whisper",
                    "transcript_runtime_mode": "degraded",
                    "transcribed_asset_count": 1,
                    "transcript_failed_asset_count": 1,
                    "transcript_excerpt_segment_count": 2,
                    "speech_fallback_segment_count": 1,
                    "speech_structure_segment_count": 2,
                    "speech_structure_question_answer_count": 1,
                    "speech_structure_monologue_count": 1,
                    "semantic_boundary_validated_count": 1,
                    "semantic_boundary_applied_count": 1,
                    "semantic_boundary_noop_count": 0,
                    "semantic_boundary_request_count": 1,
                    "semantic_boundary_threshold_targeted_count": 1,
                    "semantic_boundary_floor_targeted_count": 0,
                    "semantic_boundary_skipped_count": 0,
                    "semantic_boundary_runtime_mode": "degraded",
                    "story_assembly_active": True,
                    "story_assembly_strategy": "sequence-heuristic-v2",
                    "story_assembly_mode_alternation_count": 2,
                    "story_assembly_role_count": 3,
                    "story_assembly_prompt_fit_count": 1,
                    "story_assembly_tradeoff_count": 1,
                    "story_assembly_repetition_control_count": 1,
                    "ai_live_segment_count": 0,
                    "ai_cached_segment_count": 1,
                    "ai_fallback_segment_count": 1,
                    "ai_live_request_count": 0,
                    "ai_runtime_mode": "degraded",
                    "cache_runtime_mode": "active",
                    "runtime_reliability_mode": "degraded",
                    "runtime_ready": True,
                    "runtime_reliability_summary": "AI degraded, transcript degraded, semantic degraded, cache active",
                    "runtime_degraded_reasons": [
                        "transcript fallback on 1 asset",
                        "deterministic AI fallback on 1 segment",
                    ],
                    "runtime_intentional_skip_reasons": [
                        "AI analysis skipped 1 segment before live VLM",
                    ],
                    "dedup_group_count": 1,
                    "dedup_eliminated_count": 1,
                }
            },
            "timeline": {
                "items": [
                    {"source_reel": "A001", "sequence_role": "opener"},
                    {"source_reel": "A002", "sequence_role": "spoken beat"},
                    {"source_reel": "A003", "sequence_role": "release"},
                ]
            },
            "assets": [
                {
                    "id": "asset-1",
                    "has_proxy": True,
                    "interchange_reel_name": "A001",
                    "source_path": "/tmp/source.mov",
                }
            ],
        }

        runtime_configuration = {
            "media_dir": "/tmp/media-one",
            "media_dir_input": "./media-one",
            "ai_provider_effective": "deterministic",
            "ai_mode": "fast",
            "ai_concurrency": 4,
            "ai_effective_concurrency": 0,
            "ai_execution_context": "deterministic-fallback",
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            benchmark_root = root / "generated" / "benchmarks"
            artifact_paths = {
                "project_json": str(root / "generated" / "project.json"),
                "process_log": str(root / "generated" / "process.log"),
                "process_summary": str(root / "generated" / "process-summary.txt"),
                "process_output": str(root / "generated" / "process-output.txt"),
                "benchmark_json": str(benchmark_root / "run-002" / "benchmark.json"),
                "benchmark_history": str(benchmark_root / "history.jsonl"),
                "run_process_output": str(benchmark_root / "run-002" / "process-output.txt"),
            }

            previous = build_process_benchmark(
                run_id="run-001",
                started_at="2026-03-26T10:00:00Z",
                completed_at="2026-03-26T10:01:00Z",
                total_runtime_sec=60.0,
                project_payload=payload,
                runtime_configuration={
                    **runtime_configuration,
                    "media_dir": "/tmp/media-zero",
                    "ai_mode": "full",
                },
                artifact_paths={
                    **artifact_paths,
                    "benchmark_json": str(benchmark_root / "run-001" / "benchmark.json"),
                    "run_process_output": str(benchmark_root / "run-001" / "process-output.txt"),
                },
            )
            write_benchmark_artifacts(benchmark=previous, benchmark_root=benchmark_root)

            current = build_process_benchmark(
                run_id="run-002",
                started_at="2026-03-26T10:02:00Z",
                completed_at="2026-03-26T10:02:48Z",
                total_runtime_sec=48.0,
                project_payload=payload,
                runtime_configuration=runtime_configuration,
                artifact_paths=artifact_paths,
            )
            comparison = compare_benchmarks(
                current,
                load_previous_matching_benchmark_entry(
                    benchmark_root / "history.jsonl",
                    dataset_fingerprint=current.runtime_configuration["dataset_identity"]["fingerprint"],
                    exclude_run_id="run-002",
                ),
            )
            benchmark_path = write_benchmark_artifacts(benchmark=current, benchmark_root=benchmark_root)
            write_process_log(path=artifact_paths["process_log"], benchmark=current)

            benchmark_payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
            log_text = Path(artifact_paths["process_log"]).read_text(encoding="utf-8")
            summary_lines = build_process_summary_lines(
                project_payload=payload,
                benchmark=current,
                comparison=comparison,
            )

            self.assertEqual(benchmark_payload["run_id"], "run-002")
            self.assertEqual(
                benchmark_payload["artifact_paths"]["process_output"],
                artifact_paths["process_output"],
            )
            self.assertEqual(
                benchmark_payload["artifact_paths"]["run_process_output"],
                artifact_paths["run_process_output"],
            )
            self.assertIn("process_output=", log_text)
            self.assertIn("run_process_output=", log_text)
            self.assertIsNotNone(comparison)
            self.assertEqual(comparison.baseline_run_id, "run-001")
            self.assertIn("Benchmark comparison: vs run-001", "\n".join(summary_lines))
            self.assertIn("Comparison context: media root changed", "\n".join(summary_lines))
            self.assertIn("AI execution: configured concurrency 4, effective concurrency 0, deterministic-fallback", "\n".join(summary_lines))
            self.assertIn("AI cache activity: warm-cache (0 live, 1 cached, 0 live requests)", "\n".join(summary_lines))
            self.assertIn(
                "Deterministic preprocessing cache: warm-preprocessing (1 reused, 0 rebuilt)",
                "\n".join(summary_lines),
            )
            self.assertIn("Runtime reliability:", "\n".join(summary_lines))
            self.assertIn("Overall mode: degraded", "\n".join(summary_lines))
            self.assertIn("Runtime degraded modes: transcript fallback on 1 asset; deterministic AI fallback on 1 segment", "\n".join(summary_lines))
            self.assertIn("Runtime intentional skips: AI analysis skipped 1 segment before live VLM", "\n".join(summary_lines))
            self.assertIn("Transcript runtime: partial-fallback (faster-whisper)", "\n".join(summary_lines))
            self.assertIn("Deterministic preprocessing reuse: 1 reused, 0 rebuilt", "\n".join(summary_lines))
            self.assertIn("Speech fallback segments: 1", "\n".join(summary_lines))
            self.assertIn("Speech structure: 2 structured beats, 1 question/answer, 1 monologue", "\n".join(summary_lines))
            self.assertIn("Semantic boundary validation: 1 validated, 1 applied, 0 no-op", "\n".join(summary_lines))
            self.assertIn("Semantic boundary requests: 1", "\n".join(summary_lines))
            self.assertIn("Story assembly: sequence-heuristic-v2, 2 mode alternations, 3 roles, 1 prompt-fit beats, 1 tradeoffs", "\n".join(summary_lines))
            self.assertIn("Story assembly anchors: open on A001 (opener), release on A003 (release)", "\n".join(summary_lines))
            self.assertEqual(benchmark_payload["runtime_stability"]["overall_mode"], "degraded")
            self.assertTrue((benchmark_root / "history.jsonl").is_file())
            history_entries = [
                json.loads(line)
                for line in (benchmark_root / "history.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(history_entries[-1]["runtime_configuration"]["ai_effective_concurrency"], 0)
            self.assertEqual(history_entries[-1]["workload_counts"]["semantic_boundary_request_count"], 1)
            self.assertEqual(
                history_entries[-1]["workload_counts"]["deterministic_preprocessing_cache_hit_asset_count"],
                1,
            )

    def test_matching_benchmark_lookup_ignores_other_datasets(self) -> None:
        payload_one = {
            "project": {"analysis_summary": {}},
            "assets": [{"id": "asset-1", "interchange_reel_name": "A001", "source_path": "/tmp/a.mov"}],
        }
        payload_two = {
            "project": {"analysis_summary": {}},
            "assets": [{"id": "asset-2", "interchange_reel_name": "B001", "source_path": "/tmp/b.mov"}],
        }
        runtime_configuration = {
            "media_dir": "/tmp/media-one",
            "media_dir_input": "./media-one",
            "ai_provider_effective": "deterministic",
            "ai_mode": "fast",
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            benchmark_root = root / "generated" / "benchmarks"
            artifact_paths = {
                "project_json": str(root / "generated" / "project.json"),
                "process_log": str(root / "generated" / "process.log"),
                "process_summary": str(root / "generated" / "process-summary.txt"),
                "process_output": str(root / "generated" / "process-output.txt"),
                "benchmark_json": str(benchmark_root / "run-001" / "benchmark.json"),
                "benchmark_history": str(benchmark_root / "history.jsonl"),
                "run_process_output": str(benchmark_root / "run-001" / "process-output.txt"),
            }
            benchmark_one = build_process_benchmark(
                run_id="run-001",
                started_at="2026-03-26T10:00:00Z",
                completed_at="2026-03-26T10:00:10Z",
                total_runtime_sec=10.0,
                project_payload=payload_one,
                runtime_configuration=runtime_configuration,
                artifact_paths=artifact_paths,
            )
            benchmark_two = build_process_benchmark(
                run_id="run-002",
                started_at="2026-03-26T10:01:00Z",
                completed_at="2026-03-26T10:01:10Z",
                total_runtime_sec=12.0,
                project_payload=payload_two,
                runtime_configuration={**runtime_configuration, "media_dir": "/tmp/media-two", "media_dir_input": "./media-two"},
                artifact_paths={**artifact_paths, "benchmark_json": str(benchmark_root / "run-002" / "benchmark.json")},
            )
            write_benchmark_artifacts(benchmark=benchmark_one, benchmark_root=benchmark_root)
            write_benchmark_artifacts(benchmark=benchmark_two, benchmark_root=benchmark_root)

            matched = load_previous_matching_benchmark_entry(
                benchmark_root / "history.jsonl",
                dataset_fingerprint=benchmark_two.runtime_configuration["dataset_identity"]["fingerprint"],
                exclude_run_id="run-002",
            )
            self.assertIsNone(matched)

    def test_attach_quality_evaluation_updates_benchmark_and_history(self) -> None:
        payload = {
            "project": {
                "analysis_summary": {
                    "phase_timings_sec": {"per_asset_analysis": 4.2},
                    "candidate_segment_count": 3,
                }
            },
            "assets": [{"id": "asset-1"}],
        }
        runtime_configuration = {
            "media_dir": "/tmp/media-one",
            "media_dir_input": "./media-one",
            "ai_provider_effective": "deterministic",
            "ai_mode": "fast",
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            benchmark_root = root / "generated" / "benchmarks"
            artifact_paths = {
                "project_json": str(root / "generated" / "project.json"),
                "process_log": str(root / "generated" / "process.log"),
                "process_summary": str(root / "generated" / "process-summary.txt"),
                "process_output": str(root / "generated" / "process-output.txt"),
                "benchmark_json": str(benchmark_root / "run-001" / "benchmark.json"),
                "benchmark_history": str(benchmark_root / "history.jsonl"),
                "run_process_output": str(benchmark_root / "run-001" / "process-output.txt"),
            }
            benchmark = build_process_benchmark(
                run_id="run-001",
                started_at="2026-03-26T10:00:00Z",
                completed_at="2026-03-26T10:00:10Z",
                total_runtime_sec=10.0,
                project_payload=payload,
                runtime_configuration=runtime_configuration,
                artifact_paths=artifact_paths,
            )
            write_benchmark_artifacts(benchmark=benchmark, benchmark_root=benchmark_root)
            summary_path = root / "generated" / "segmentation-evaluation-summary.txt"
            evaluation_result = {
                "fixture_set": "fixture-a",
                "passed": True,
                "summary": {
                    "check_count": 5,
                    "passed_check_count": 5,
                    "failed_check_count": 0,
                },
                "semantic_validation": {
                    "dormant": False,
                    "validated_count": 1,
                    "applied_count": 1,
                    "floor_targeted_count": 0,
                },
                "timeline_results": {
                    "passed": True,
                    "checks": [
                        {"passed": True},
                        {"passed": False},
                    ],
                    "observed": {
                        "item_count": 8,
                        "opener_source_reel": "DJI_0721",
                    },
                },
            }

            evaluation_path = attach_quality_evaluation(
                benchmark_root=benchmark_root,
                run_id="run-001",
                evaluation_result=evaluation_result,
                summary_path=summary_path,
            )

            benchmark_payload = json.loads((benchmark_root / "run-001" / "benchmark.json").read_text(encoding="utf-8"))
            history_entries = [
                json.loads(line)
                for line in (benchmark_root / "history.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(evaluation_path.name, "segmentation-evaluation.json")
            self.assertEqual(benchmark_payload["quality_evaluation"]["fixture_set"], "fixture-a")
            self.assertEqual(
                benchmark_payload["artifact_paths"]["segmentation_evaluation_summary"],
                str(summary_path),
            )
            self.assertEqual(history_entries[-1]["quality_evaluation_summary"]["fixture_set"], "fixture-a")
            self.assertEqual(history_entries[-1]["quality_evaluation_summary"]["semantic_validation"]["validated_count"], 1)
            self.assertTrue(history_entries[-1]["quality_evaluation_summary"]["timeline"]["passed"])
            self.assertEqual(history_entries[-1]["quality_evaluation_summary"]["timeline"]["failed_check_count"], 1)
            self.assertEqual(
                history_entries[-1]["quality_evaluation_summary"]["timeline"]["observed"]["opener_source_reel"],
                "DJI_0721",
            )

    def test_benchmark_history_serializes_runtime_stability_context(self) -> None:
        payload = {
            "project": {
                "analysis_summary": {
                    "runtime_reliability_mode": "partial",
                    "runtime_ready": True,
                    "runtime_reliability_summary": "AI active, transcript partial, semantic active, cache active",
                    "ai_runtime_mode": "active",
                    "transcript_runtime_mode": "partial",
                    "semantic_boundary_runtime_mode": "active",
                    "cache_runtime_mode": "active",
                    "runtime_degraded_reasons": [],
                    "runtime_intentional_skip_reasons": ["transcript targeting kept cost bounded: 2 transcript-target skips"],
                }
            },
            "assets": [{"id": "asset-1", "interchange_reel_name": "A001", "source_path": "/tmp/a.mov"}],
        }
        runtime_configuration = {
            "media_dir": "/tmp/media-one",
            "media_dir_input": "./media-one",
            "ai_provider_effective": "deterministic",
            "ai_mode": "fast",
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            benchmark_root = root / "generated" / "benchmarks"
            artifact_paths = {
                "project_json": str(root / "generated" / "project.json"),
                "process_log": str(root / "generated" / "process.log"),
                "process_summary": str(root / "generated" / "process-summary.txt"),
                "process_output": str(root / "generated" / "process-output.txt"),
                "benchmark_json": str(benchmark_root / "run-001" / "benchmark.json"),
                "benchmark_history": str(benchmark_root / "history.jsonl"),
                "run_process_output": str(benchmark_root / "run-001" / "process-output.txt"),
            }
            benchmark = build_process_benchmark(
                run_id="run-001",
                started_at="2026-03-26T10:00:00Z",
                completed_at="2026-03-26T10:00:10Z",
                total_runtime_sec=10.0,
                project_payload=payload,
                runtime_configuration=runtime_configuration,
                artifact_paths=artifact_paths,
            )
            write_benchmark_artifacts(benchmark=benchmark, benchmark_root=benchmark_root)

            history_entries = [
                json.loads(line)
                for line in (benchmark_root / "history.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(history_entries[-1]["runtime_stability"]["overall_mode"], "partial")
            self.assertEqual(
                history_entries[-1]["runtime_stability"]["component_modes"]["transcript"],
                "partial",
            )
            self.assertEqual(
                history_entries[-1]["runtime_stability"]["intentional_skip_reasons"],
                ["transcript targeting kept cost bounded: 2 transcript-target skips"],
            )

    def test_benchmark_comparison_reports_cache_warmth_and_execution_context(self) -> None:
        baseline = {
            "run_id": "run-001",
            "total_runtime_sec": 30.0,
            "runtime_configuration": {
                "media_dir": "/tmp/media-one",
                "ai_provider_effective": "lmstudio",
                "ai_mode": "fast",
                "ai_effective_concurrency": 2,
                "ai_execution_context": "configured-parallel-requests",
            },
            "runtime_stability": {
                "overall_mode": "active",
                "component_modes": {
                    "ai": "active",
                    "transcript": "active",
                    "semantic_boundary": "active",
                    "cache": "inactive",
                },
            },
            "dataset_identity": {"fingerprint": "dataset-1", "label": "media-one"},
            "workload_counts": {
                "asset_count": 1,
                "candidate_segment_count": 2,
                "deterministic_preprocessing_cache_hit_asset_count": 1,
                "deterministic_preprocessing_cache_rebuilt_asset_count": 0,
                "semantic_boundary_request_count": 2,
                "ai_live_segment_count": 2,
                "ai_cached_segment_count": 0,
            },
        }
        current = build_process_benchmark(
            run_id="run-002",
            started_at="2026-03-26T10:02:00Z",
            completed_at="2026-03-26T10:02:20Z",
            total_runtime_sec=20.0,
            project_payload={
                "project": {
                    "analysis_summary": {
                        "candidate_segment_count": 2,
                        "deterministic_preprocessing_cache_hit_asset_count": 0,
                        "deterministic_preprocessing_cache_rebuilt_asset_count": 1,
                        "semantic_boundary_request_count": 1,
                        "ai_live_segment_count": 0,
                        "ai_cached_segment_count": 2,
                        "ai_runtime_mode": "active",
                        "transcript_runtime_mode": "active",
                        "semantic_boundary_runtime_mode": "active",
                        "cache_runtime_mode": "active",
                        "runtime_reliability_mode": "active",
                        "runtime_ready": True,
                        "runtime_reliability_summary": "AI active, transcript active, semantic active, cache active",
                    }
                },
                "assets": [{"id": "asset-1", "interchange_reel_name": "A001", "source_path": "/tmp/a.mov"}],
            },
            runtime_configuration={
                "media_dir": "/tmp/media-one",
                "media_dir_input": "./media-one",
                "ai_provider_effective": "mlx-vlm-local",
                "ai_mode": "fast",
                "ai_concurrency": 4,
                "ai_effective_concurrency": 1,
                "ai_execution_context": "serialized-local-model",
            },
            artifact_paths={"benchmark_json": "/tmp/benchmark.json"},
        )

        comparison = compare_benchmarks(current, baseline)

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertIn("effective AI concurrency changed (2 -> 1)", comparison.context_differences)
        self.assertIn(
            "AI execution context changed (configured-parallel-requests -> serialized-local-model)",
            comparison.context_differences,
        )
        self.assertIn("semantic boundary request volume changed (2 -> 1)", comparison.context_differences)
        self.assertIn("AI cache activity changed (cold-cache -> warm-cache)", comparison.context_differences)
        self.assertIn(
            "deterministic preprocessing cache activity changed (warm-preprocessing -> cold-preprocessing)",
            comparison.context_differences,
        )


if __name__ == "__main__":
    unittest.main()
