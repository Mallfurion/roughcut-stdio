## ADDED Requirements

### Requirement: Desktop app SHALL surface degraded runtime status clearly
The desktop app SHALL surface whether the configured runtime is ready, partially degraded, or running with fallback-safe limitations when that affects local processing behavior.

#### Scenario: Optional runtime capability is degraded
- **WHEN** the desktop app can determine that a configured runtime capability is unavailable, gated, or running in fallback-safe degraded mode
- **THEN** the app SHALL disclose that status in the desktop workflow
- **THEN** the user SHALL still be able to proceed when supported fallback behavior exists
