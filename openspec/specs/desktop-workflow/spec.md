# desktop-workflow Specification

## Purpose
TBD - created by archiving change tauri-desktop-app. Update Purpose after archive.
## Requirements
### Requirement: Desktop app SHALL provide a guided local workflow
The product SHALL provide a Tauri-based desktop workflow for the local Mac usage model instead of relying on terminal-first and browser-first interaction as the primary user experience. The frontend implementation of that workflow SHALL be organized behind explicit modules for bootstrap, state, platform access, and step rendering rather than being centralized in one entrypoint file. The packaged desktop app SHALL preserve that guided workflow without requiring a checked-out repository or manual terminal-first setup.

#### Scenario: User opens the desktop app
- **WHEN** the desktop app starts
- **THEN** it SHALL provide a guided workflow for runtime choice, setup, media selection, processing, review, and export
- **THEN** the app bootstrap path SHALL delegate workflow initialization and rendering responsibilities through dedicated frontend modules
- **THEN** a packaged build SHALL not require the user to run repo setup commands manually before entering that workflow

### Requirement: Desktop app SHALL let the user choose the runtime mode
The desktop app SHALL provide a visible runtime selection step before processing begins.

#### Scenario: User reaches the start of the workflow
- **WHEN** the user begins a new session
- **THEN** the app SHALL offer `deterministic`, `lmstudio`, and `mlx-vlm-local` as runtime options
- **THEN** the selected runtime SHALL become part of the active app configuration

### Requirement: Desktop app SHALL provide native file and export dialogs
The desktop app SHALL use native operating system dialogs for media-folder selection and Resolve export destination selection.

#### Scenario: User chooses a media root
- **WHEN** the user selects footage for analysis
- **THEN** the app SHALL use a native folder picker

#### Scenario: User exports a Resolve timeline
- **WHEN** the user chooses to export the timeline
- **THEN** the app SHALL use a native save dialog to choose the export destination

### Requirement: Desktop app SHALL display process progress visually
The desktop app SHALL show visual progress and run-state information while the analyzer is processing footage.

#### Scenario: Process is running
- **WHEN** the analyzer is active
- **THEN** the app SHALL show progress state, status text, and current activity in a visual processing view

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

### Requirement: Desktop app SHALL surface degraded runtime status clearly
The desktop app SHALL surface whether the configured runtime is ready, partially degraded, or running with fallback-safe limitations when that affects local processing behavior.

#### Scenario: Optional runtime capability is degraded
- **WHEN** the desktop app can determine that a configured runtime capability is unavailable, gated, or running in fallback-safe degraded mode
- **THEN** the app SHALL disclose that status in the desktop workflow
- **THEN** the user SHALL still be able to proceed when supported fallback behavior exists

### Requirement: Desktop app SHALL expose packaged-runtime readiness
The desktop app SHALL surface whether required packaged runtime components are ready for processing and SHALL distinguish bundled runtime readiness from model-asset readiness or unavailable optional AI features.

#### Scenario: User reviews runtime health in a packaged build
- **WHEN** the desktop app checks runtime status in an installed build
- **THEN** it SHALL disclose whether the bundled packaged processing runtime is ready
- **THEN** it SHALL distinguish missing required model assets from optional runtime features that still need bootstrap or download
- **THEN** the user SHALL still be able to proceed with supported fallback modes when only optional assets are unavailable

### Requirement: Desktop app SHALL provide a startup bootstrap screen for missing model assets
The packaged desktop app SHALL check model readiness during startup and SHALL present a dedicated bootstrap screen when assets required for the currently configured packaged workflow are missing.

#### Scenario: Required packaged model asset is missing
- **WHEN** the packaged app starts and required model assets are not yet present in app-managed storage
- **THEN** it SHALL show a bootstrap screen before entering the full workflow
- **THEN** that screen SHALL describe which assets are missing and why they are needed
- **THEN** the user SHALL be able to trigger a download/retry action from that screen
- **THEN** the app SHALL re-check readiness after the download completes

### Requirement: Desktop app SHALL persist editor take overrides in the local review workflow
The desktop app SHALL let the user persist best-take editorial state for an asset during desktop review, including selecting a different active take or explicitly clearing the active take, and SHALL reuse that state when loading the active project until the user clears it or a different generated project replaces the current one.

#### Scenario: User promotes a segment to the active best take
- **WHEN** the user marks a candidate segment as the best take for its asset in desktop review
- **THEN** the desktop app SHALL persist that override locally for the active generated project
- **THEN** subsequent desktop reloads of that same generated project SHALL preserve the override-resolved selection state

#### Scenario: User clears an existing best-take override
- **WHEN** the user clears a previously stored best-take override for an asset
- **THEN** the desktop app SHALL remove the local override for that asset
- **THEN** the active selection state for that asset SHALL fall back to the analyzer-selected take set

#### Scenario: User clears the active best take for an asset
- **WHEN** the user clears the currently selected best take for an asset in desktop review
- **THEN** the desktop app SHALL persist that cleared-selection state locally for the active generated project
- **THEN** the active resolved project state SHALL contain no selected take for that asset until the editor restores analyzer state or promotes another segment

#### Scenario: Stored override does not match the current generated project
- **WHEN** the desktop app loads a generated project whose identity or candidate segment set no longer matches a stored override entry
- **THEN** the app SHALL ignore that incompatible override entry
- **THEN** the active review state SHALL continue from the generated project without applying stale editorial state
