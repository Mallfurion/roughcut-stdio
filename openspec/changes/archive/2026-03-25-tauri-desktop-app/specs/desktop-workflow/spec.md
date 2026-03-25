# desktop-workflow Specification

## ADDED Requirements

### Requirement: Desktop app SHALL provide a guided local workflow
The product SHALL provide a Tauri-based desktop workflow for the local Mac usage model instead of relying on terminal-first and browser-first interaction as the primary user experience.

#### Scenario: User opens the desktop app
- **WHEN** the desktop app starts
- **THEN** it SHALL provide a guided workflow for runtime choice, setup, media selection, processing, review, and export

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
