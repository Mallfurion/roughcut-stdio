## MODIFIED Requirements

### Requirement: Process runs SHALL persist structured benchmark records
Each successful `npm run process` invocation SHALL persist a structured benchmark record under `generated/benchmarks/` for that run. The record SHALL include a unique run identifier, start and completion timestamps, total elapsed runtime, major pipeline phase durations, workload counts, and effective runtime configuration needed to compare runs. When semantic boundary validation is enabled, the benchmark record SHALL preserve enough semantic-targeting metrics to explain whether the pass was dormant, active, or runtime-bound.

#### Scenario: Benchmark record captures semantic-validation activation
- **WHEN** semantic boundary validation is enabled for a completed run
- **THEN** the benchmark record SHALL include eligible, validated, skipped, fallback, and no-op or changed-validation counts when available
