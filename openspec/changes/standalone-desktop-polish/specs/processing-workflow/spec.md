## ADDED Requirements

### Requirement: Packaged processing SHALL register reusable run metadata
The packaged desktop process workflow SHALL persist run metadata that is sufficient to reopen packaged runs from a run library.

#### Scenario: Packaged run metadata is written
- **WHEN** a packaged desktop process run completes successfully
- **THEN** the app SHALL persist run metadata that identifies the generated project, diagnostics, runtime summary, and benchmark artifacts for that run
- **THEN** the run metadata SHALL remain usable even after newer packaged runs are created

### Requirement: Packaged processing SHALL preserve imported runs as library entries
The packaged desktop workflow SHALL preserve compatible imported repo-generated runs as packaged run-library entries when import succeeds.

#### Scenario: Repo-generated run is imported into packaged storage
- **WHEN** the app imports a compatible generated run from repo-local state
- **THEN** the imported run SHALL be registered in the packaged run library
- **THEN** the imported run SHALL remain reviewable without rerunning analyzer processing
