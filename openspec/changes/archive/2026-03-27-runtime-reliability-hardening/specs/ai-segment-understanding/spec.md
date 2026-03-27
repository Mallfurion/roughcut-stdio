## ADDED Requirements

### Requirement: System SHALL make AI-path activation and fallback explicit
The analyzer SHALL preserve explicit state for whether expensive AI-related paths activated, were skipped, were gated, or degraded to fallback behavior during a run.

#### Scenario: Optional AI path is gated or skipped
- **WHEN** an optional AI-related path does not run because of shortlisting, readiness, or runtime gating
- **THEN** generated project state or process diagnostics SHALL preserve that reason
- **THEN** downstream inspection SHALL be able to distinguish intentional gating from failure

#### Scenario: Optional AI path degrades to fallback
- **WHEN** a configured AI-related path cannot complete and the analyzer falls back to deterministic behavior
- **THEN** generated state or diagnostics SHALL preserve the degraded-to-fallback status
- **THEN** the run SHALL remain inspectable enough to explain that change in behavior
