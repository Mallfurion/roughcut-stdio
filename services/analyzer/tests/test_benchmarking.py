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
    load_previous_benchmark_entry,
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
                    "candidate_segment_count": 4,
                    "prefilter_shortlisted_count": 2,
                    "vlm_target_count": 1,
                    "filtered_before_vlm_count": 1,
                    "audio_signal_asset_count": 1,
                    "audio_silent_asset_count": 0,
                    "transcript_status": "partial-fallback",
                    "transcript_provider_effective": "faster-whisper",
                    "transcribed_asset_count": 1,
                    "transcript_failed_asset_count": 1,
                    "transcript_excerpt_segment_count": 2,
                    "speech_fallback_segment_count": 1,
                    "semantic_boundary_validated_count": 1,
                    "semantic_boundary_applied_count": 1,
                    "semantic_boundary_noop_count": 0,
                    "semantic_boundary_threshold_targeted_count": 1,
                    "semantic_boundary_floor_targeted_count": 0,
                    "semantic_boundary_skipped_count": 0,
                    "ai_live_segment_count": 0,
                    "ai_cached_segment_count": 1,
                    "ai_fallback_segment_count": 1,
                    "ai_live_request_count": 0,
                    "dedup_group_count": 1,
                    "dedup_eliminated_count": 1,
                }
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
            comparison = compare_benchmarks(current, load_previous_benchmark_entry(benchmark_root / "history.jsonl"))
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
            self.assertIn("Transcript runtime: partial-fallback (faster-whisper)", "\n".join(summary_lines))
            self.assertIn("Speech fallback segments: 1", "\n".join(summary_lines))
            self.assertIn("Semantic boundary validation: 1 validated, 1 applied, 0 no-op", "\n".join(summary_lines))
            self.assertTrue((benchmark_root / "history.jsonl").is_file())

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


if __name__ == "__main__":
    unittest.main()
