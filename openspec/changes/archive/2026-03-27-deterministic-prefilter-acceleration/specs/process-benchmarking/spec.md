## MODIFIED Requirements

### Requirement: Process runs SHALL persist structured benchmark records
Each successful `npm run process` invocation SHALL persist a structured benchmark record under `generated/benchmarks/` for that run. The record SHALL include a unique run identifier, start and completion timestamps, total elapsed runtime, major pipeline phase durations, workload counts, and effective runtime configuration needed to compare runs. When segmentation-quality evaluation or semantic boundary validation is active, the benchmark record SHALL also preserve the resulting quality and semantic-impact metrics for that run, including any sequence-level quality summary produced by the evaluation harness. When AI cache reuse, provider-specific execution limits, or deterministic preprocessing cache reuse materially affect runtime, the benchmark record SHALL also preserve enough activity counters to distinguish cached work, live work, semantic-validation request volume, configured-vs-effective execution context, and deterministic preprocessing reuse for the run.

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
- **THEN** the benchmark record SHALL include eligible, targeted, validated, skipped, fallback, and no-op or changed-validation counts when available
- **THEN** the benchmark record SHALL also include semantic-validation request volume when model-backed validation work was attempted

#### Scenario: Benchmark record captures cache-warm AI activity
- **WHEN** a completed run mixes cached AI work, live AI work, or provider-specific execution limits
- **THEN** the benchmark record SHALL preserve counters that distinguish those paths
- **THEN** the record SHALL preserve effective execution context when it differs materially from configured concurrency

#### Scenario: Benchmark record captures deterministic preprocessing reuse
- **WHEN** a completed run reuses persisted deterministic preprocessing artifacts for scene, frame, or audio screening inputs
- **THEN** the benchmark record SHALL preserve counters or context that distinguish reused preprocessing work from freshly rebuilt preprocessing work
- **THEN** the record SHALL remain able to explain whether front-half runtime improvements came from deterministic preprocessing reuse, AI cache warmth, or both

### Requirement: Benchmark artifacts SHALL preserve runtime-stability context
Benchmark artifacts SHALL preserve enough runtime-stability context to explain why a run changed in cost or capability, including cache usage, degraded-mode activation, major gating decisions, and warm-vs-cold AI or deterministic preprocessing context when available.

#### Scenario: Run uses cache or degraded fallback
- **WHEN** a completed run uses meaningful cache reuse or enters a degraded fallback mode for an optional capability
- **THEN** the benchmark artifacts SHALL preserve that context
- **THEN** the run summary SHALL be able to distinguish those cases from a fully fresh or fully healthy run

#### Scenario: Expensive path is gated off
- **WHEN** a completed run skips a major optional path because of readiness, budget, or gating rules
- **THEN** the benchmark artifacts SHALL preserve the gating context that explains the skip
- **THEN** runtime comparisons SHALL not reduce the difference to elapsed time alone

#### Scenario: Warm-cache run is compared with a cold-cache run
- **WHEN** the system compares completed benchmark runs where cache warmth materially changed the AI workload
- **THEN** the comparison context SHALL preserve that difference
- **THEN** the run summary SHALL remain able to distinguish cache-driven speedups from cold-path efficiency improvements

#### Scenario: Warm preprocessing run is compared with a cold preprocessing run
- **WHEN** the system compares completed benchmark runs where deterministic preprocessing artifact reuse materially changed the front-half screening workload
- **THEN** the comparison context SHALL preserve that difference separately from AI cache warmth
- **THEN** the run summary SHALL remain able to distinguish deterministic preprocessing speedups from later AI-path efficiency improvements
