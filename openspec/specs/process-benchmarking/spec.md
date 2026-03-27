# process-benchmarking Specification

## Purpose
Define the persistent benchmark artifacts and run-to-run comparison behavior for the process pipeline.

## Requirements
### Requirement: Process runs SHALL persist structured benchmark records
Each successful `npm run process` invocation SHALL persist a structured benchmark record under `generated/benchmarks/` for that run. The record SHALL include a unique run identifier, start and completion timestamps, total elapsed runtime, major pipeline phase durations, workload counts, and effective runtime configuration needed to compare runs. When segmentation-quality evaluation or semantic boundary validation is active, the benchmark record SHALL also preserve the resulting quality and semantic-impact metrics for that run, including any sequence-level quality summary produced by the evaluation harness.

#### Scenario: Successful process run creates benchmark artifacts
- **WHEN** `npm run process` completes successfully
- **THEN** the repository SHALL contain `generated/benchmarks/history.jsonl`
- **THEN** the repository SHALL contain `generated/benchmarks/<run-id>/benchmark.json`
- **THEN** `generated/benchmarks/<run-id>/benchmark.json` SHALL include total runtime and phase-level timing for media discovery, per-asset analysis, take selection, and timeline assembly

#### Scenario: Benchmark record captures comparison context
- **WHEN** a benchmark record is written for a completed process run
- **THEN** the record SHALL include the effective AI provider and AI mode used for that run
- **THEN** the record SHALL include workload context sufficient to explain timing differences, including at least asset count and candidate segment count
- **THEN** the record SHALL include paths to the generated artifacts associated with that run

#### Scenario: Benchmark record captures segmentation-quality context
- **WHEN** a benchmark record is written for a process or evaluation run that collects segmentation-quality metrics
- **THEN** the record SHALL include transcript-targeting, transcript-probing, transcript-excerpt, speech-fallback, and semantic-validation counters when available
- **THEN** the record SHALL preserve any fixture-set identifier used for that run
- **THEN** the record SHALL preserve any sequence-level evaluation summary produced for that run

#### Scenario: Benchmark record captures semantic-validation activation
- **WHEN** semantic boundary validation is enabled for a completed run
- **THEN** the benchmark record SHALL include eligible, validated, skipped, fallback, and no-op or changed-validation counts when available

### Requirement: Process benchmarks SHALL support run-to-run comparisons
The benchmark system SHALL compare a completed process run with prior benchmark history when prior completed runs exist. The comparison SHALL be surfaced in the process summary using the persisted benchmark records rather than ad hoc terminal parsing.

#### Scenario: Prior benchmark history exists
- **WHEN** `npm run process` completes successfully and at least one prior completed benchmark record exists
- **THEN** the process summary SHALL report the current run's total runtime relative to a previous run
- **THEN** the comparison SHALL include the previous run identifier and total runtime delta
- **THEN** the comparison SHALL disclose comparison-context differences when the current run and baseline run used different effective provider, AI mode, or asset count

#### Scenario: No prior benchmark history exists
- **WHEN** `npm run process` completes successfully and no prior completed benchmark record exists
- **THEN** the process summary SHALL indicate that no prior benchmark is available for comparison
- **THEN** the absence of a prior benchmark SHALL not cause the process run to fail or warn

### Requirement: Benchmark comparisons SHALL include quality context
When a benchmarked run includes evaluation results, the comparison workflow SHALL preserve enough quality context to explain whether a faster or slower run also changed output quality.

#### Scenario: Compared runs include evaluation output
- **WHEN** the system compares a completed benchmarked run against prior history and both runs have quality-evaluation data
- **THEN** the comparison output SHALL include the fixture set and high-level quality result for each run
- **THEN** the comparison SHALL not reduce the run summary to runtime deltas alone

### Requirement: Benchmark artifacts SHALL preserve runtime-stability context
Benchmark artifacts SHALL preserve enough runtime-stability context to explain why a run changed in cost or capability, including cache usage, degraded-mode activation, and major gating decisions when available.

#### Scenario: Run uses cache or degraded fallback
- **WHEN** a completed run uses meaningful cache reuse or enters a degraded fallback mode for an optional capability
- **THEN** the benchmark artifacts SHALL preserve that context
- **THEN** the run summary SHALL be able to distinguish those cases from a fully fresh or fully healthy run

#### Scenario: Expensive path is gated off
- **WHEN** a completed run skips a major optional path because of readiness, budget, or gating rules
- **THEN** the benchmark artifacts SHALL preserve the gating context that explains the skip
- **THEN** runtime comparisons SHALL not reduce the difference to elapsed time alone
