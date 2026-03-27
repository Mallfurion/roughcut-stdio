## Why

The standalone desktop runtime is now implemented, but the installed app still feels like a first shipped version rather than a polished desktop product. The next gaps are not core processing gaps; they are operational gaps around recovery, migration, run access, and release packaging reliability.

## What Changes

- Add an installed-app runtime management surface so the user can inspect bundled runtime health, model asset state, storage usage, and repair or re-download runtime assets without falling back to terminal workflows.
- Add first-launch migration/import behavior for existing repo-local settings and generated state so a developer or early user can move into packaged mode without manually reconfiguring everything.
- Add a packaged run library so the desktop app can reopen and inspect prior generated runs instead of only the active/latest run.
- Stabilize packaged release output, especially DMG creation and verification, so release builds do not depend on fragile Finder-layout steps or partially successful bundle side effects.
- Extend packaged verification and release checklists to cover installer output, first-launch migration, runtime repair, and reopening prior runs.

## Capabilities

### New Capabilities
- `desktop-runtime-management`: Manage packaged runtime health, downloaded assets, storage, repair actions, and first-launch migration/import inside the desktop app.
- `desktop-run-library`: Browse, reopen, and inspect previous packaged runs from app-managed storage.

### Modified Capabilities
- `desktop-workflow`: The desktop workflow will gain first-launch migration/import, runtime-management entrypoints, and packaged run-library navigation.
- `processing-workflow`: Packaged processing will preserve enough run metadata for a reusable run library rather than only the active/latest run.
- `review-workspace`: Desktop review will support loading previous generated runs in addition to the active run.
- `standalone-desktop-runtime`: Packaged runtime behavior will expand to cover migration/import, repair/update actions, and release-packaging reliability requirements.

## Impact

- `apps/desktop/src` desktop navigation, startup flow, settings/runtime UI, and review loading
- `apps/desktop/src-tauri` runtime metadata, migration/import commands, run indexing, and packaging scripts
- packaged storage layout and run metadata under app-managed directories
- DMG/build packaging configuration and release verification tooling
- documentation for packaged migration, repair, run-library behavior, and release packaging
