## ADDED Requirements

### Requirement: Desktop app SHALL expose transcript support controls
The desktop app SHALL expose transcript support settings when they affect local processing behavior and SHALL persist those settings into the analyzer configuration used for process runs.

#### Scenario: User opens advanced process settings
- **WHEN** the user reviews advanced analyzer settings before a process run
- **THEN** the desktop app SHALL expose transcript support configuration
- **THEN** the selected transcript configuration SHALL be persisted for the process run

#### Scenario: Transcript support is unavailable on the current machine
- **WHEN** the desktop app can determine that transcript support is unavailable or disabled
- **THEN** the app SHALL show that transcript-backed analysis will not run
- **THEN** the user SHALL still be able to proceed with transcript-free processing

