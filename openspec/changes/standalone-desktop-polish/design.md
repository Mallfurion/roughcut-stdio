## Context

The packaged desktop runtime now works, but the current installed-app experience is still narrow. It assumes the user will either start fresh or tolerate manual recovery steps, and it only exposes the active/latest generated run even though packaged storage already contains richer run artifacts. Release packaging is also still brittle at the DMG layer because it depends on Finder-layout automation that can fail after the app bundle itself has already been produced successfully.

This change is a product-polish follow-up to the standalone runtime work. It does not revisit the core packaged-runtime abstraction, bundled sidecars, or model bootstrap architecture. Instead, it makes the installed app easier to adopt, maintain, and trust as a real desktop product.

## Goals / Non-Goals

**Goals:**
- Import useful repo-local settings and generated state into packaged mode on first launch.
- Let the installed app inspect runtime health, downloaded assets, storage use, and repair/re-download actions without terminal fallback.
- Preserve enough metadata for packaged runs to reopen prior runs from a run library.
- Make packaged release output reliable enough that `.app` and DMG builds do not depend on fragile Finder automation.
- Extend verification and docs around migration, repair, run reopening, and release packaging.

**Non-Goals:**
- Replacing the existing runtime abstraction or bundled-runtime model.
- Adding cloud sync, account state, or remote run storage.
- Building a full media-asset catalog independent of generated runs.
- Changing analyzer scoring, segmentation, or Resolve export semantics.
- Implementing auto-update delivery for the desktop app itself.

## Decisions

### 1. Treat migration as an explicit first-launch import, not an implicit background rewrite

Packaged mode will detect candidate repo-local state on first launch and offer an explicit import flow. The app will import:
- repo `.env` / `.env.local` values that map to packaged settings
- compatible generated run artifacts from repo `generated/`
- optional benchmark history where the file shape matches packaged expectations

The app will not mutate or delete repo-local state during import.

Rationale:
- Early adopters and developers are likely to have meaningful repo-local state already.
- Explicit import is safer than silently rewriting settings or moving generated files.

Alternatives considered:
- Silent one-time migration: rejected because it hides data movement and complicates support.
- No import path: rejected because it makes the packaged app feel disconnected from prior use.

### 2. Persist a packaged run index instead of inferring the run library from ad hoc files

Each packaged run will write a small run manifest alongside existing generated artifacts and append/update a run index in app-managed storage. The run index will include:
- run id
- started/completed timestamps
- dataset/media-root identity
- project name / story prompt summary
- artifact paths
- runtime summary and degraded/fallback labels

The run library UI will read that index rather than scanning arbitrary directories heuristically.

Rationale:
- Run reopening needs stable metadata and predictable ordering.
- The current benchmark and generated artifacts are rich enough, but they are not a clean UI index by themselves.

Alternatives considered:
- Directory scan only: rejected because it is more fragile and less queryable.
- Database-backed run library: rejected as unnecessary complexity for current local scope.

### 3. Add a dedicated runtime-management surface in the desktop app

The desktop app will expose a runtime-management view or dialog that shows:
- bundled runtime readiness
- downloaded asset readiness
- current configured provider/runtime mode
- storage locations and approximate sizes
- repair/re-check/re-download actions
- migration/import status

Repair actions will reuse the existing packaged setup/bootstrap orchestration rather than introducing a second runtime-management backend.

Rationale:
- Packaged users need a recovery path inside the app.
- The current startup bootstrap card is useful at first launch but too narrow for ongoing maintenance.

Alternatives considered:
- Keep all runtime repair on the startup card: rejected because ongoing maintenance is broader than startup blocking state.
- Push runtime repair to docs only: rejected because it undermines the standalone-product goal.

### 4. Keep the review model run-centric

The run library will reopen previous generated runs as read-only review sources with the same review/export semantics the active run already has. Editor overrides may remain scoped to the selected run’s generated project identity.

This change will not introduce a higher-level “project library” abstraction beyond run-centric history.

Rationale:
- The generated project is already the natural review/export unit.
- A run library is enough to solve the immediate “I need to reopen a previous result” problem.

Alternatives considered:
- Project/workspace abstraction first: rejected because it is a larger product concept with unclear requirements.

### 5. Make `.app` the primary packaging success condition and DMG a hardened secondary artifact

Release packaging will treat a valid app bundle as the primary build output. DMG creation will be hardened so automated builds avoid Finder prettifying steps that are known to fail intermittently. The DMG path should use a non-interactive, CI-safe configuration by default for automated packaging and verification.

Rationale:
- The app bundle is the actual product artifact; DMG is a distribution wrapper.
- The recent bundling failure showed that Finder-driven layout can fail after producing an installable app.

Alternatives considered:
- Keep the current fancy DMG path unchanged: rejected because it has already shown fragile behavior.
- Drop DMG entirely: rejected because DMG is still a reasonable macOS distribution format.

## Risks / Trade-offs

- [Imported repo state may not match packaged expectations] -> Keep import explicit, validate artifact shape, and surface skipped items rather than failing the whole import.
- [Run index drift could make prior runs disappear or look stale] -> Derive manifests at run completion and rebuild the index from manifests when needed.
- [Runtime-management actions could blur required vs optional assets] -> Preserve the current explicit readiness model and label repair actions by asset/runtime class.
- [Run library can increase UI complexity] -> Keep the initial library narrow: searchable/sortable run list plus reopen action.
- [Simpler DMG packaging may lose cosmetic layout] -> Prefer reliable automated packaging over Finder-prettified presentation.

## Migration Plan

1. Add run-manifest and run-index writing to packaged process completion.
2. Add commands for listing runs, loading a selected run, inspecting runtime state, and importing repo-local state.
3. Add first-launch migration/import UI plus a runtime-management surface in the desktop frontend.
4. Update review/export loading to work from selected packaged runs, not only the active/latest run.
5. Harden packaging scripts so automated builds produce a reliable app bundle and CI-safe DMG output.
6. Extend verification scripts and docs for import, repair, run reopening, and packaging checks.

## Open Questions

- Should repo-state import be offered only on first launch, or also later from the runtime-management surface?
- Should the run library allow deleting old packaged runs in this same change, or only viewing/reopening them?
- Should DMG packaging remain enabled by default in local builds, or should the default local release target become `.app` with DMG as an opt-in step?
