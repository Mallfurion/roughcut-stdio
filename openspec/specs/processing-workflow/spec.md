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
The process workflow SHALL report deduplication statistics in addition to existing prefilter and VLM reduction statistics. This reporting SHALL be included in `generated/process.log` and in the summary printed at the end of a process run.

#### Scenario: Process run produces deduplicated candidates
- **WHEN** `npm run process` completes and at least one candidate was eliminated by deduplication
- **THEN** the process summary SHALL report the total number of candidates generated across all assets
- **THEN** the process summary SHALL report the number of candidates eliminated by deduplication
- **THEN** the process summary SHALL report the number of candidates forwarded to shortlist selection after deduplication

#### Scenario: No candidates are deduplicated
- **WHEN** all candidate segments in the run are visually distinct
- **THEN** the process summary SHALL indicate that zero candidates were eliminated by deduplication
- **THEN** no warning or error SHALL be emitted for the absence of deduplication activity

