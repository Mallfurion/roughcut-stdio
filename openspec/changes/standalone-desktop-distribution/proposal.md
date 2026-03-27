## Why

Roughcut Stdio already has a real Tauri desktop app, but it still behaves like a development shell around the repository rather than a standalone product. The app depends on repo-relative scripts, a local Python virtual environment, and developer-managed setup steps, which blocks normal desktop distribution.

## What Changes

- Package the desktop app around an app-managed runtime instead of a checked-out repository workspace.
- Move setup, runtime checks, processing, and export orchestration from repo shell scripts toward desktop-managed commands and bundled sidecars.
- Define app-owned paths for generated output, logs, settings, caches, and model storage.
- Preserve deterministic fallback, transcript support, and export reliability inside the packaged app workflow.
- Keep npm/script-based development workflows available for repository development and debugging.

## Capabilities

### New Capabilities
- `standalone-desktop-runtime`: Package and run Roughcut Stdio as a self-contained desktop app with bundled runtime components, app-managed storage, and first-run bootstrap behavior.

### Modified Capabilities
- `desktop-workflow`: The desktop app must support a standalone packaged workflow instead of assuming a checked-out repository and developer shell environment.
- `processing-workflow`: Desktop-managed processing must work without repo-relative shell orchestration while preserving generated artifacts, diagnostics, and export behavior.

## Impact

- `apps/desktop/src-tauri`
- desktop packaging and release configuration
- analyzer runtime invocation and resource discovery
- app-managed config/cache/output locations
- setup/bootstrap flow for Python runtime, ffmpeg, transcript support, and optional local AI assets
