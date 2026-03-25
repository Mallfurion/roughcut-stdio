## Context

The current product still exposes its primary interaction model through npm scripts and a browser review surface. That is acceptable for development, but it is not aligned with the intended product: a local Mac application that analyzes footage, shows progress visually, presents reviewed segments and grades, and exports a Resolve-ready timeline directly.

The desktop migration should change the user interaction model without discarding the working local analyzer pipeline. The Python analyzer, generated project state, and Resolve export path already exist and should remain the processing core. The change is primarily about orchestration, UI surface, and local application packaging.

## Goals

- Make the desktop application the primary user-facing product surface.
- Use Tauri as the local app shell on macOS.
- Replace the current browser-first review app target with a new desktop UI built specifically for this workflow.
- Keep the Python analyzer as the analysis and export engine.
- Keep setup as a pre-launch step and provider configuration outside the app.
- Preserve deterministic fallback and current generated state formats where practical.

## Non-Goals

- Rewriting the analyzer in Rust.
- Shipping a full nonlinear editor in the first desktop version.
- Keeping the existing web app as a co-equal product surface.
- Redesigning Resolve export format in this change.

## Decisions

### 1. Use Tauri as the application shell

Tauri should own:

- app lifecycle
- native folder picker for media root selection
- native save dialog for Resolve export
- process/export command execution
- progress and status event delivery to the frontend

This gives the app native local capability boundaries without requiring users to open a terminal.

### 2. Keep the Python analyzer as the processing core

The desktop app should call the existing analyzer scripts or a thin analyzer command API rather than rewriting media analysis logic in Rust. The analyzer remains responsible for:

- media discovery
- prefilter and shortlist construction
- AI provider use
- timeline generation
- Resolve export generation

The desktop app should become the orchestrator and state presenter.

### 3. Build a new desktop UI instead of reusing the current web app

The current web app is useful reference material, but the desktop app should be treated as a new UI surface with a simpler guided workflow:

1. media folder selection
2. process run with visible progress
3. result review by clip and section
4. export

This avoids carrying browser-first assumptions into the final product.

### 4. Keep setup out of the desktop interaction flow

Setup should remain explicit, but it should happen before the desktop app is opened. The default setup path should install shared local requirements and the embedded MLX/MLX-VLM path by default.

Runtime/provider selection should remain outside the app through env configuration. The desktop app may still expose narrow per-run controls, such as AI mode selection, when they directly affect a processing run.

### 5. Standardize desktop-analyzer communication

The desktop app needs reliable progress and status, but the current implementation uses stdout parsing to surface progress and state. The long-term direction is still a stable machine-readable event protocol that includes:

- media discovery counts
- processing phase
- current asset
- elapsed time / ETA where available
- completion/failure payloads

This should be preferred over scraping loosely formatted terminal output, even though stdout parsing is acceptable in the current implementation slice.

## Architecture

### Desktop App

Tauri app responsibilities:

- maintain app state for selected media folder, selected AI mode, process state, review state, and export destination
- call process/export commands
- receive and render progress events
- render results from generated project state

### Analyzer Backend

Python responsibilities remain:

- setup helpers for local runtime preparation
- media analysis
- AI provider use
- generated project state
- FCPXML export

### Shared State Boundary

The initial desktop version can continue to use `generated/project.json` as the main review payload, but desktop orchestration should own when and where that state is created and loaded.

### Export Boundary

Export should continue to produce `FCPXML`, but the save destination should be chosen in the desktop app via native dialog instead of relying on a fixed repo path as the primary user flow.

## Risks

- Tauri orchestration can become fragile if it depends on unstable stdout parsing.
  - Mitigation: define structured progress/status output early.

- Moving to a new desktop UI can temporarily regress existing review features.
  - Mitigation: focus first on workflow completeness, then richer review affordances.

- Setup can become slow or opaque if too much work is hidden.
  - Mitigation: make setup phase-by-phase and visibly report what is being installed or verified.

- Desktop packaging and Python environment management can become brittle.
  - Mitigation: keep setup explicit, local, and testable in development before packaging concerns expand.

## Migration Order

1. Add desktop capability and workflow specs.
2. Scaffold a Tauri app workspace.
3. Implement desktop media folder selection.
4. Implement desktop process runner with progress reporting.
5. Implement desktop review/results surface around clips and sections.
6. Implement desktop export flow with native save dialog.
7. Keep setup as a pre-launch workflow outside the app.
8. Improve the analyzer event protocol beyond stdout parsing.
