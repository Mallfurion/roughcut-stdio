## ADDED Requirements

### Requirement: Packaged desktop app SHALL index packaged runs
The packaged desktop app SHALL preserve a run index for packaged process runs so previous runs can be listed and reopened without rescanning arbitrary storage directories.

#### Scenario: Packaged process run completes
- **WHEN** a packaged desktop process run finishes
- **THEN** the app SHALL persist run metadata that identifies the run, its timestamps, runtime summary, and artifact paths
- **THEN** the packaged run SHALL become available in the run library

### Requirement: Packaged desktop app SHALL let the user reopen prior runs
The packaged desktop app SHALL let the user reopen a previous packaged run from the run library as a review source.

#### Scenario: User reopens a previous run
- **WHEN** the user selects a previous packaged run from the run library
- **THEN** the desktop review flow SHALL load that run's generated project and associated review/export artifacts
- **THEN** reopening a previous run SHALL not require rerunning processing
