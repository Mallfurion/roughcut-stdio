## MODIFIED Requirements

### Requirement: Process SHALL honor configured media roots and write generated artifacts
The process step SHALL read footage from `TIMELINE_MEDIA_DIR` when set and SHALL otherwise fall back to the repository `media/` path. The process step SHALL write generated state under `generated/`, including a project JSON document, processing diagnostics, and the persisted terminal-facing output for the latest run.

#### Scenario: Media root is provided through environment
- **WHEN** `TIMELINE_MEDIA_DIR` is set for a process run
- **THEN** the process step SHALL scan that absolute directory instead of the repository `media/` path

#### Scenario: Process completes successfully
- **WHEN** `npm run process` finishes
- **THEN** the repository SHALL contain `generated/project.json`
- **THEN** the repository SHALL contain `generated/process.log`
- **THEN** the repository SHALL contain `generated/process-summary.txt`
- **THEN** the repository SHALL contain `generated/process-output.txt`

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
