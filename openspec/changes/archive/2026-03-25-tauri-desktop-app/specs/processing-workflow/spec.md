# processing-workflow Specification

## MODIFIED Requirements

### Requirement: Repository SHALL expose an npm-first workflow
The repository workflow SHALL continue to support preparing and validating the configured AI backend through npm-first commands for development and debugging, but the primary product workflow SHALL move to desktop-managed orchestration.

#### Scenario: Desktop app performs setup
- **WHEN** the desktop app prepares the local environment
- **THEN** it SHALL use the same underlying setup capabilities as the repository workflow without requiring the user to run npm commands manually

#### Scenario: Desktop app starts a process run
- **WHEN** the desktop app launches a process run
- **THEN** the analyzer SHALL execute under desktop orchestration rather than requiring terminal-first interaction

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report which effective backend is used and whether AI results came from live inference, cache reuse, or fallback, and that reporting SHALL be consumable by the desktop application as structured run-state.

#### Scenario: Desktop app consumes process status
- **WHEN** a process run is started from the desktop app
- **THEN** the analyzer SHALL provide status information that the desktop app can present as a progress view instead of relying only on human-oriented terminal output
