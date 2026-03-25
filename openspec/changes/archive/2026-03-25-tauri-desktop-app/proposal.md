## Why

The current repository has already moved away from the browser review surface and now has a working Tauri desktop shell. However, the original proposal for this change still describes an earlier direction where the app would own runtime selection and setup inside the desktop flow. That is no longer the implemented product shape.

The current product direction is:

- the app should run locally on macOS
- local setup should happen before launch with `npm run setup`
- runtime/provider configuration should remain outside the app through env configuration
- the desktop app should focus on the footage workflow itself
- the desktop app should let the user pick footage visually
- the desktop app should run analysis and show progress visually
- the desktop app should present clip sections, scores, and VLM output in the same interface
- the desktop app should export a DaVinci-ready timeline from that interface

Because the app must control local processes, local files, and export paths in a polished way, a desktop shell is a better fit than a browser-first web app. Tauri remains the right direction because it keeps the UI stack lightweight while allowing native file pickers, process management, and local system integration.

## What Changes

- Replace the current browser-first app target with a Tauri desktop app target.
- Remove the standalone web app from the product direction and make the desktop app the primary user-facing interface.
- Keep the Python analyzer as the local processing engine, but run it under desktop orchestration for the footage workflow.
- Add a guided local workflow with these steps:
  1. choose media folder with a native file picker
  2. start processing and show visual progress/status
  3. review clips and sections with scores and VLM rationale
  4. export a Resolve timeline using a native save dialog
- Keep setup and provider/runtime configuration outside the desktop app:
  - `npm run setup` prepares the local environment before launch
  - env configuration selects `deterministic`, `lmstudio`, or `mlx-vlm-local`
  - the desktop app may expose narrow per-run controls such as `TIMELINE_AI_MODE=fast|full`
- Make media-folder selection, processing state, review state, and export state part of the desktop app model rather than requiring terminal usage.
- Preserve the current local-first architecture, deterministic fallback behavior, and Resolve export path while changing the interaction model around them.

## User Flow

### Flow: Local Setup Before Launch

The desktop workflow SHALL assume that setup has already been performed before opening the app.

Examples:

- install Python/runtime dependencies
- prepare `ffmpeg`
- install the embedded MLX-VLM runtime requirements by default
- prepare embedded model files when `mlx-vlm-local` is configured

Provider selection remains external to the desktop app through local environment configuration.

### Flow: Choose Media Folder

The desktop app SHALL use a native folder picker so the user can choose the footage root without editing `TIMELINE_MEDIA_DIR` manually.

The app SHALL show the number of discovered video files for the selected folder before processing.

### Flow: Process With Visual Progress

The desktop app SHALL start the local analyzer process and present:

- asset counts
- per-run status text
- progress bar or equivalent visual progress indicator
- expandable process logs

The app SHALL expose a per-run AI mode selector for:

- `fast`
- `full`

### Flow: Review Results

After processing, the desktop app SHALL show:

- clips as the top-level review unit
- collapsible clip rows
- sections for each clip when a row is opened
- per-section score
- provider context
- keep label / confidence
- VLM summary and rationale

This review surface replaces the previous browser-oriented best-take and timeline-preview presentation.

### Flow: Export Resolve Timeline

The desktop app SHALL provide an export action named for Resolve timeline export, use a native save dialog, and write a Resolve-ready timeline file to the chosen location.

`FCPXML` remains the primary export target unless later changed by a separate spec.

## Capabilities

### New Capabilities

- `desktop-workflow`: Tauri-based local application shell, native folder/save dialogs, process execution, and visual run-state management.

### Modified Capabilities

- `processing-workflow`: move from terminal-first footage orchestration to desktop-managed processing while preserving the same local analyzer pipeline.
- `review-workspace`: replace the standalone web app target with a desktop review surface organized around clips and sections.
- `resolve-export`: export from the desktop application through a native save flow instead of requiring npm/CLI usage.

## Impact

- Affected code:
  - a new Tauri desktop app workspace
  - desktop-to-analyzer orchestration layer
  - process/status reporting interfaces
  - desktop review UI built specifically for clip/section inspection
  - existing setup/process/export entrypoints, which remain implementation details behind the desktop workflow
- Affected outputs:
  - process status model
  - reviewed project state
  - exported `FCPXML`
- Dependencies and systems:
  - Tauri
  - native file/folder dialogs on macOS
  - local Python analyzer process management
  - env-managed AI provider configuration
  - existing Resolve export path

## Open Questions And Assumptions

- Assume the first supported platform is macOS only.
- Assume the Python analyzer remains the processing engine and is not rewritten in Rust.
- Assume the desktop UI is a new Tauri app rather than a reuse of the previous web UI.
- Assume setup installs the embedded MLX / MLX-VLM path and shared local requirements by default before the app is launched.
- Assume review in the current desktop version focuses on results inspection and export, not full NLE-style timeline editing.
