# processing-workflow Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: Repository SHALL expose an npm-first workflow
The repository SHALL provide a simple command flow centered on `npm run setup`, `npm run process`, `npm run view`, and `npm run export`. The repository SHALL also provide `npm run check:ai` for validating the optional local AI provider before processing.

#### Scenario: User follows the primary command flow
- **WHEN** the user is testing the repository from a clean checkout
- **THEN** the documented happy path SHALL be `setup -> process -> view -> export`

#### Scenario: User wants to validate LM Studio before a full run
- **WHEN** the user has configured `TIMELINE_AI_PROVIDER=lmstudio`
- **THEN** `npm run check:ai` SHALL report provider status and fail if LM Studio was requested but is not reachable

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
The process step SHALL report media discovery, AI provider configuration, fallback decisions, discovered file counts, matched asset counts, and progress through the asset list.

#### Scenario: LM Studio is unavailable
- **WHEN** `TIMELINE_AI_PROVIDER=lmstudio` is configured but LM Studio is unreachable
- **THEN** the process output SHALL state that LM Studio is unavailable
- **THEN** the process output SHALL state that deterministic analysis is being used instead

#### Scenario: Multiple assets are being processed
- **WHEN** a process run analyzes more than one asset
- **THEN** the CLI SHALL show asset progress with elapsed time and estimated remaining time

