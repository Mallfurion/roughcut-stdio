# processing-workflow Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: Repository SHALL expose an npm-first workflow
The repository workflow SHALL continue to support preparing and validating the configured AI backend through npm-first commands for development and debugging, but the primary product workflow SHALL move to desktop-managed orchestration. The packaged desktop app SHALL execute setup, processing, and export through app-managed orchestration rather than relying on repo-relative shell scripts.

#### Scenario: Desktop app performs setup
- **WHEN** the desktop app prepares the local environment
- **THEN** it SHALL use the same underlying setup capabilities as the repository workflow without requiring the user to run npm commands manually
- **THEN** a packaged build SHALL invoke app-managed runtime setup rather than repo-relative shell scripts as its required execution path

#### Scenario: Desktop app starts a process run
- **WHEN** the desktop app launches a process run
- **THEN** the analyzer SHALL execute under desktop orchestration rather than requiring terminal-first interaction
- **THEN** a packaged build SHALL use bundled or app-managed runtime components instead of assuming a repo `.venv`

### Requirement: Packaged process workflow SHALL preserve generated artifacts and diagnostics
The packaged desktop workflow SHALL preserve the same project-level generated state, processing diagnostics, benchmark artifacts, and export-oriented artifacts that the repository workflow exposes, even when those artifacts are written to app-managed storage.

#### Scenario: Packaged process run completes
- **WHEN** the user completes a process run from an installed desktop build
- **THEN** the app SHALL persist a generated project document, process diagnostics, benchmark history, and exportable timeline state
- **THEN** those artifacts SHALL remain inspectable to the desktop workflow even if their storage location differs from the repository `generated/` path

### Requirement: Packaged process workflow SHALL translate packaged settings into runtime configuration
The packaged desktop workflow SHALL persist packaged settings outside repo `.env` files and SHALL translate those settings into analyzer/runtime configuration when packaged commands execute.

#### Scenario: Packaged app runs with saved settings
- **WHEN** the user saves runtime settings in an installed desktop build
- **THEN** the app SHALL persist those settings in app-managed configuration storage
- **THEN** a subsequent packaged process or export run SHALL use those persisted settings without requiring a repository `.env` file

### Requirement: Process SHALL honor configured media roots and write generated artifacts
The process step SHALL read footage from `TIMELINE_MEDIA_DIR` when set and SHALL otherwise fall back to the repository `media/` path. The process step SHALL write generated state under `generated/`, including a project JSON document, processing diagnostics, and the persisted terminal-facing output for the latest run. When project-level story assembly is active, generated state SHALL preserve the sequence rationale used for the final rough timeline.

#### Scenario: Process completes with project-level story assembly
- **WHEN** `npm run process` finishes with story-assembly logic enabled
- **THEN** `generated/project.json` SHALL preserve sequence-level rationale or grouping metadata for the final timeline

### Requirement: Process SHALL preserve richer story-assembly diagnostics
When project-level story assembly is active, generated process artifacts SHALL preserve more than the final order alone. They SHALL also preserve the assembly rationale or diagnostics needed to understand why the final sequence was chosen.

#### Scenario: Process completes with enhanced story assembly
- **WHEN** `npm run process` finishes with richer story-assembly logic enabled
- **THEN** `generated/project.json` SHALL preserve sequence-level rationale for the final timeline
- **THEN** the generated diagnostics or summaries SHALL preserve enough assembly context to explain major sequencing tradeoffs

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

### Requirement: Process SHALL preserve explicit degraded-runtime reporting
The process workflow SHALL preserve explicit status for degraded or fallback runtime behavior rather than only reporting successful activation paths.

#### Scenario: Optional runtime path is unavailable
- **WHEN** a configured optional runtime path cannot be used during processing
- **THEN** generated process artifacts SHALL preserve a named degraded or fallback status for that path
- **THEN** processing SHALL continue when deterministic fallback is supported

#### Scenario: Optional runtime path is skipped by gating
- **WHEN** the analyzer intentionally skips an expensive optional path because of gating, budget, or readiness rules
- **THEN** generated process artifacts SHALL preserve that skip or gating reason
- **THEN** the skip SHALL remain distinguishable from a hard failure
