# processing-workflow Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: Repository SHALL expose an npm-first workflow
The repository workflow SHALL continue to support preparing and validating the configured AI backend through npm-first commands for development and debugging, but the primary product workflow SHALL move to desktop-managed orchestration.

#### Scenario: Desktop app performs setup
- **WHEN** the desktop app prepares the local environment
- **THEN** it SHALL use the same underlying setup capabilities as the repository workflow without requiring the user to run npm commands manually

#### Scenario: Desktop app starts a process run
- **WHEN** the desktop app launches a process run
- **THEN** the analyzer SHALL execute under desktop orchestration rather than requiring terminal-first interaction

### Requirement: Process SHALL honor configured media roots and write generated artifacts
The process step SHALL read footage from `TIMELINE_MEDIA_DIR` when set and SHALL otherwise fall back to the repository `media/` path. The process step SHALL write generated state under `generated/`, including a project JSON document and processing diagnostics.

#### Scenario: Media root is provided through environment
- **WHEN** `TIMELINE_MEDIA_DIR` is set for a process run
- **THEN** the process step SHALL scan that absolute directory instead of the repository `media/` path

#### Scenario: Process completes successfully
- **WHEN** `npm run process` finishes
- **THEN** the repository SHALL contain `generated/project.json`
- **THEN** the repository SHALL contain `generated/process.log`

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report which effective backend is used and whether AI results came from live inference, cache reuse, or fallback, and that reporting SHALL be consumable by the desktop application as structured run-state.

#### Scenario: Desktop app consumes process status
- **WHEN** a process run is started from the desktop app
- **THEN** the analyzer SHALL provide status information that the desktop app can present as a progress view instead of relying only on human-oriented terminal output

