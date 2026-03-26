# process-benchmarking Specification

## Purpose
Define the persistent benchmark artifacts and run-to-run comparison behavior for the process pipeline.

## Requirements
### Requirement: Process runs SHALL persist structured benchmark records
Each successful `npm run process` invocation SHALL persist a structured benchmark record under `generated/benchmarks/` for that run. The record SHALL include a unique run identifier, start and completion timestamps, total elapsed runtime, major pipeline phase durations, workload counts, and effective runtime configuration needed to compare runs.

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
