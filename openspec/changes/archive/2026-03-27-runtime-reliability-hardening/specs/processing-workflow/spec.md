## ADDED Requirements

### Requirement: Process SHALL preserve explicit degraded-runtime reporting
The process workflow SHALL preserve explicit status for degraded or fallback runtime behavior rather than only reporting successful activation paths.

#### Scenario: Optional runtime path is unavailable
- **WHEN** a configured optional runtime path cannot be used during processing
- **THEN** generated process artifacts SHALL preserve a named degraded or fallback status for that path
- **THEN** processing SHALL continue when deterministic fallback is supported

#### Scenario: Optional runtime path is skipped by gating
- **WHEN** the analyzer intentionally skips an expensive optional path because of gating, budget, or readiness rules
- **THEN** generated process artifacts SHALL preserve that skip or gating reason
- **THEN** the skip SHALL remain distinguishable from a hard failure
