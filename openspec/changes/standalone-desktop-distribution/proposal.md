## Why

Roughcut Stdio already has a real Tauri desktop app, but it still behaves like a development shell around the repository rather than a standalone product. The app depends on repo-relative scripts, a local Python virtual environment, and developer-managed setup steps, which blocks normal desktop distribution.

## What Changes

- Package the desktop app around an app-managed runtime instead of a checked-out repository workspace.
- Bundle the required desktop runtime dependencies inside the app distribution, including the Python runtime, analyzer environment, `ffmpeg`/`ffprobe`, and export helpers needed for normal processing.
- Move setup, runtime checks, processing, and export orchestration from repo shell scripts toward desktop-managed commands and bundled sidecars.
- Define app-owned paths for generated output, logs, settings, caches, and model storage.
- Add packaged-app runtime readiness checks that distinguish bundled runtime readiness from model-asset readiness.
- Add a first-run bootstrap screen that checks for required model assets in app-managed storage and offers a download action when they are missing.
- Keep downloaded models outside the signed app bundle in app-managed storage so the installed app can update runtime assets without repackaging the application binary.
- Preserve deterministic fallback, transcript support, and export reliability inside the packaged app workflow, including a reduced-capability path when optional runtime assets are unavailable or skipped.
- Keep npm/script-based development workflows available for repository development and debugging.

## Capabilities

### New Capabilities
- `standalone-desktop-runtime`: Package and run Roughcut Stdio as a self-contained desktop app with bundled runtime components, app-managed storage, startup readiness checks, and first-run bootstrap/download behavior for model assets.

### Modified Capabilities
- `desktop-workflow`: The desktop app must support a standalone packaged workflow instead of assuming a checked-out repository and developer shell environment.
- `processing-workflow`: Desktop-managed processing must work without repo-relative shell orchestration while preserving generated artifacts, diagnostics, and export behavior.

## Impact

- `apps/desktop/src-tauri`
- desktop packaging and release configuration
- analyzer runtime invocation and resource discovery
- app-managed config/cache/output locations
- startup bootstrap/download flow for required and optional model assets
- setup/bootstrap flow for Python runtime, ffmpeg, transcript support, and optional local AI assets
