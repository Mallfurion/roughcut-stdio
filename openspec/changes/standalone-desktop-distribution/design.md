## Context

Roughcut Stdio already ships a desktop UI, but the current product still assumes a development repository layout. The desktop backend resolves the workspace root, shells out to repo scripts, and expects a local Python virtual environment, generated directory, and developer-managed setup flow. That is acceptable for local development, but it is not a normal desktop distribution model.

The standalone version needs to preserve the current local-first pipeline, transcript and AI runtime controls, deterministic fallback, and Resolve export reliability while removing the assumption that the user has a checked-out repository or knows how to run setup commands manually.

## Goals / Non-Goals

**Goals:**
- Run the desktop product without requiring a repository checkout or terminal-first setup.
- Ship a packaged build with the core processing runtime available immediately after install.
- Check model readiness at startup and guide the user through downloading missing model assets.
- Move generated output, logs, settings, caches, and model storage to app-managed directories.
- Keep deterministic fallback, transcript-free processing, and Resolve export behavior intact.
- Preserve repo/npm workflows for development even after the packaged app exists.

**Non-Goals:**
- Rewriting the analyzer core in Rust.
- Bundling every optional local AI model directly into the signed app payload.
- Building a full project/run library browser in this change.
- Changing the editorial behavior of segmentation, scoring, review, or export.
- Removing the existing repository workflow used by developers.

## Decisions

### 1. Bundle the core processing runtime inside the packaged app

The packaged app will include the required runtime dependencies for normal processing:
- Python 3.12+ runtime
- packaged analyzer environment
- `ffmpeg` and `ffprobe`
- export helpers and analyzer scripts required by review/export flows

The installed app must not depend on host Python, Homebrew-installed `ffmpeg`, or a repo `.venv` to launch and process footage.

Rationale:
- A standalone app must be immediately runnable after install.
- The current analyzer already depends on Python plus `ffmpeg`/`ffprobe`, so bundling those components is lower risk than redesigning the pipeline.

Alternatives considered:
- Rely on host Python and host `ffmpeg`: rejected because it recreates a developer installation experience.
- Rewrite the runtime in Rust: rejected because it is a larger product rewrite, not a packaging step.

### 2. Use a shared runtime abstraction with separate packaged and repo backends

The desktop backend will own orchestration through one runtime abstraction with two execution modes:
- `PackagedRuntime`: app-managed paths, bundled runtime, packaged bootstrap/download flow
- `RepoRuntime`: current repo-relative scripts and developer-oriented paths for local development

The packaged backend must not invoke repo shell scripts as its required execution path. The repo backend may continue to use the existing scripts while the packaged path is stabilized.

Rationale:
- This preserves the current development workflow while creating a clean packaged-product path.
- It limits risk by avoiding a forced all-at-once rewrite of development tooling.

Alternatives considered:
- Force both packaged and dev modes through the same new orchestration immediately: rejected because it couples packaging work to dev-tooling migration.
- Keep shell scripts as the packaged entrypoint: rejected because they encode repo assumptions.

### 3. Separate core runtime readiness from model-asset readiness

Startup readiness will be split into two categories:
- bundled runtime readiness: whether the installed app has the packaged runtime required to process
- model-asset readiness: whether model weights or caches needed for the configured workflow are present

The app must surface these states separately in packaged builds.

Rationale:
- Runtime binaries and model assets have different packaging, update, and failure characteristics.
- This gives the desktop UI a precise readiness model instead of one opaque “available/unavailable” status.

### 4. Download model assets into app-managed storage through a startup bootstrap screen

Large model assets will not be embedded in the signed app bundle by default. Instead, the app will:
- check app-managed model storage on startup
- determine which assets are required for the currently configured packaged workflow
- show a bootstrap/download screen when required assets are missing
- download those assets into app-managed storage
- retry readiness checks after download completes

The packaged default workflow will treat the default CLIP semantic-scoring weights and the default transcript runtime model as first-run bootstrap assets. Provider-specific assets such as MLX-VLM models remain optional and download only when the user enables that provider.

Rationale:
- The current setup already bootstraps CLIP and conditionally prepares transcript or MLX-VLM assets.
- Keeping large assets outside the signed app reduces installer size and avoids repackaging the app for model changes.

Alternatives considered:
- Bundle all model assets in the app: rejected for size, signing, and update complexity.
- Download assets silently in the background: rejected because the product should make runtime preparation explicit and user-controlled.

### 5. Keep the packaged core runtime offline-capable after install

The packaged app must be able to launch, configure, and run deterministic processing without network access after installation. Network access is acceptable only for downloading missing model assets that are not already present.

Rationale:
- The product is explicitly local-first.
- This keeps installation reliability separate from optional runtime bootstrap.

### 6. Store packaged settings outside repo `.env` files

Repo mode will continue to use `.env` and `.env.local` as its source of truth. Packaged mode will persist equivalent settings in app-managed configuration storage and translate them into process environment variables only at execution time.

Rationale:
- A packaged app may not have a writable or meaningful repo root.
- Reusing the existing environment-variable contract internally reduces analyzer changes while separating packaged storage from repo files.

### 7. Move generated output to app-managed project/run directories

The packaged app will own these storage locations:
- settings and persisted configuration
- generated project artifacts for the active run
- logs and benchmark history
- model and transcript caches
- temporary work files

Export output will still be written to a user-selected destination. The packaged review flow only needs to expose the active/latest generated run in this change; a full run-history browser is out of scope.

Rationale:
- This matches normal desktop-app behavior.
- It preserves the current “active generated project” review model while avoiding a larger library-management feature.

### 8. Preserve deterministic and reduced-capability paths

If optional runtime assets are unavailable, skipped, or fail to download, the app must continue to support deterministic or reduced-capability processing where the analyzer already supports it. Missing assets that are required for the currently selected packaged workflow should block entry into that workflow until the bootstrap step succeeds or the user changes configuration to a supported fallback mode.

Rationale:
- Current analyzer behavior already degrades when transcript or AI runtimes are unavailable.
- The packaged UI needs a clear rule for when to block and when to allow fallback.

## Risks / Trade-offs

- [Bundled runtime increases packaging complexity] -> Keep the analyzer as a sidecar runtime and bundle only the dependencies needed for normal processing.
- [Model downloads can fail or confuse users] -> Make bootstrap explicit, versioned, retryable, checksum-verified, and status-driven.
- [Packaged and repo workflows may drift] -> Use a shared runtime abstraction and keep behavior-level specs anchored in OpenSpec.
- [App-managed storage changes output paths] -> Keep artifact formats stable and scope v1 review to the active/latest run.
- [Default first-run downloads may increase time-to-first-process] -> Make the startup bootstrap screen explicit and keep deterministic fallback available when the selected workflow allows it.
- [macOS packaging/signing adds release overhead] -> Treat signing, notarization, and installer verification as part of the rollout plan.

## Migration Plan

1. Introduce the runtime abstraction and split packaged/runtime path resolution from repo-development paths.
2. Move packaged settings and storage to app-managed directories while preserving repo `.env` behavior in development mode.
3. Replace packaged setup, runtime checks, processing, and export with desktop-managed orchestration over the bundled runtime.
4. Bundle Python, analyzer environment, `ffmpeg`/`ffprobe`, and export helpers as packaged resources/sidecars.
5. Add startup readiness checks plus a bootstrap/download screen for missing model assets.
6. Verify packaged builds for offline deterministic processing, model bootstrap, transcript-disabled processing, and Resolve export reliability.
7. Add packaging, signing, notarization, and release documentation for the standalone app.

## Open Questions

No blocking product questions remain for implementation of this change. Future follow-up work may revisit:
- whether the packaged app should expose a full previous-runs browser
- whether model updates should later support background refresh flows
