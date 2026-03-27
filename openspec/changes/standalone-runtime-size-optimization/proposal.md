## Why

The packaged standalone app is functionally complete, but the built bundle is too large for a normal desktop distribution workflow. Most of that size comes from the packaged Python runtime and site-packages payload, which makes downloads, installs, updates, and release artifacts heavier than they need to be.

## What Changes

- Redefine the packaged desktop app around a slim deterministic core bundle instead of shipping every optional runtime dependency in the initial install.
- Move heavy optional capabilities into downloadable runtime packs, starting with transcript support, CLIP semantic scoring, and MLX-VLM local AI support.
- Replace whole-`.venv` packaging with a runtime-only packaged Python environment built specifically for the installed app.
- Prune the packaged Python home and runtime payload to remove development files, docs, GUI frameworks, and other non-runtime content that are not needed by the standalone app.
- Add bundle-size auditing, size budgets, and verification so release builds can detect payload regressions before distribution.

## Capabilities

### New Capabilities
- `desktop-runtime-payloads`: Define the packaged runtime payload model, including slim core runtime contents, optional downloadable feature packs, and payload verification budgets.

### Modified Capabilities
- `standalone-desktop-runtime`: The packaged runtime requirements will change from “bundle everything needed for all modes” to “ship a deterministic core and install optional heavyweight runtimes on demand.”
- `desktop-workflow`: The startup/runtime workflow will need to distinguish shipped core runtime from installable optional feature packs.
- `processing-workflow`: Packaged processing will need to honor which optional runtime packs are installed and preserve fallback behavior when a requested pack is unavailable.

## Impact

- `apps/desktop/src-tauri/build.rs` and Tauri bundle resource staging
- packaged Python/runtime layout and dependency selection
- runtime bootstrap and runtime-management UX in the desktop app
- analyzer packaging dependencies and runtime verification scripts
- release packaging documentation and size-regression checks
