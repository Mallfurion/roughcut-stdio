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
The process step SHALL read footage from `TIMELINE_MEDIA_DIR` when set and SHALL otherwise fall back to the repository `media/` path. The process step SHALL write generated state under `generated/`, including a project JSON document, processing diagnostics, and the persisted terminal-facing output for the latest run. When project-level story assembly is active, generated state SHALL preserve the sequence rationale used for the final rough timeline.

#### Scenario: Process completes with project-level story assembly
- **WHEN** `npm run process` finishes with story-assembly logic enabled
- **THEN** `generated/project.json` SHALL preserve sequence-level rationale or grouping metadata for the final timeline

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report benchmark timing statistics in addition to existing prefilter, deduplication, audio, and VLM reduction statistics. This reporting SHALL be included in `generated/process-summary.txt`, in the terminal-facing output saved to `generated/process-output.txt`, and in the benchmark artifacts for the completed run.

#### Scenario: Process run has benchmark history available
- **WHEN** `npm run process` completes and at least one prior benchmark record exists
- **THEN** the process summary SHALL report the current run's total elapsed time
- **THEN** the process summary SHALL report at least one prior-run comparison for that elapsed time
- **THEN** the terminal-facing output saved for the run SHALL include the same benchmark summary shown to the operator

#### Scenario: Process run has no benchmark history available
- **WHEN** `npm run process` completes and no prior benchmark record exists
- **THEN** the process summary SHALL still report the current run's total elapsed time
- **THEN** the process summary SHALL indicate that no prior benchmark is available for comparison
- **THEN** the absence of benchmark history SHALL not cause a warning or failure

### Requirement: Process SHALL report transcript runtime status
The process workflow SHALL report transcript runtime configuration and transcript availability alongside existing AI/runtime diagnostics in generated process artifacts and terminal-facing output. This reporting SHALL include whether assets were targeted for full transcription, skipped, loaded from transcript cache, probed, or rejected after probing.

#### Scenario: Transcript support is enabled and available
- **WHEN** `npm run process` starts with transcript support enabled and a supported backend available
- **THEN** process output SHALL disclose that transcript extraction is active
- **THEN** generated process artifacts SHALL record transcript runtime status for the run

#### Scenario: Selective transcript probing is active
- **WHEN** the analyzer uses transcript targeting or short transcript probes during a process run
- **THEN** generated process artifacts SHALL record counts for targeted, skipped, probed, probe-rejected, transcribed, and cached transcript assets
- **THEN** terminal-facing process output SHALL include the same counters in the run summary

#### Scenario: Transcript support is enabled but unavailable
- **WHEN** `npm run process` starts with transcript support enabled but the configured backend cannot be used
- **THEN** process output SHALL disclose that transcript extraction is unavailable and that fallback behavior will be used
- **THEN** generated process artifacts SHALL preserve that transcript-unavailable status after the run

