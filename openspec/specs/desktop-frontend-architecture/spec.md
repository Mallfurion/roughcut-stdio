# desktop-frontend-architecture Specification

## Purpose
TBD - created by archiving change desktop-frontend-modularization. Update Purpose after archive.

## Requirements
### Requirement: Desktop frontend modules SHALL separate workflow concerns
The desktop frontend SHALL organize workflow state, Tauri integration, rendering, and shared helpers into distinct modules rather than centralizing those responsibilities in the top-level entrypoint.

#### Scenario: App bootstraps the desktop workflow
- **WHEN** the desktop app starts
- **THEN** the top-level entry module SHALL delegate initialization, state bootstrapping, and Tauri event wiring to dedicated frontend modules
- **THEN** the guided choose/process/results workflow SHALL remain behaviorally equivalent to the current desktop flow

### Requirement: Desktop review rendering SHALL be isolated from the app shell
The desktop frontend SHALL keep review-specific project composition and segment-card rendering behind dedicated review modules so review changes do not require editing the top-level workflow shell.

#### Scenario: App renders generated project results
- **WHEN** the desktop app loads a generated project for the results step
- **THEN** clip grouping, recommendation joining, and segment-card rendering SHALL be composed by review-focused modules
- **THEN** the results step SHALL continue to display the existing review facts needed for export-oriented inspection
