## ADDED Requirements

### Requirement: Desktop review SHALL load packaged historical runs
The desktop review workspace SHALL support loading a previous packaged run from the run library in addition to the active/latest generated run.

#### Scenario: User reviews a historical packaged run
- **WHEN** the user opens a previous packaged run from the run library
- **THEN** the review workspace SHALL load that run's generated project as the active review source
- **THEN** the review workspace SHALL preserve the same recommendation, override, and export semantics already used for the active generated run
