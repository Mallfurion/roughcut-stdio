## ADDED Requirements

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
