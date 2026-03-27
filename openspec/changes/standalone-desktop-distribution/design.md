## Context

Roughcut Stdio already ships a desktop UI, but the current product still assumes a development repository layout. The desktop backend resolves the workspace root, shells out to repo scripts, and expects a local Python virtual environment, generated directory, and developer-managed setup flow. That is acceptable for local development, but it is not a normal desktop distribution model.

The standalone version needs to preserve the current local-first pipeline, transcript and AI runtime controls, deterministic fallback, and Resolve export reliability while removing the assumption that the user has a checked-out repository or knows how to run setup commands manually.

## Goals / Non-Goals

**Goals:**
- Run the desktop product without requiring a repository checkout or terminal-first setup.
- Bundle or sidecar the runtime components required for normal desktop processing.
- Move generated output, logs, settings, caches, and model storage to app-managed directories.
- Keep deterministic fallback, transcript-free processing, and Resolve export behavior intact.
- Preserve repo/npm workflows for development even after the packaged app exists.

**Non-Goals:**
- Rewriting the analyzer core in Rust.
- Bundling every optional local AI model directly into the app binary.
- Changing the editorial behavior of segmentation, scoring, review, or export.
- Removing the existing repository workflow used by developers.

## Decisions

### 1. Package the analyzer as a bundled sidecar runtime

The standalone app will keep the current Python analyzer architecture, but it will invoke a bundled Python runtime and packaged analyzer environment rather than a repo `.venv` or shell script entrypoint.

Rationale:
- This preserves the existing analyzer implementation and shipped behavior.
- It is much lower risk than rewriting the analyzer in another language.
- It keeps local-first processing intact while making packaging practical.

Alternatives considered:
- Rewrite the analyzer in Rust: rejected because it is a much larger product rewrite, not a packaging step.
- Keep relying on host Python and pip: rejected because it still produces a developer-style installation experience.

### 2. Make the desktop app the owner of runtime orchestration

The Tauri backend will become the canonical orchestrator for setup checks, first-run bootstrap, process execution, and export execution. Repo shell scripts may remain for development, but the packaged app must not require them.

Rationale:
- A packaged app should not assume repo-relative shell entrypoints.
- This gives the desktop product direct control over status, errors, logs, and migration behavior.

Alternatives considered:
- Keep shell scripts as the primary entrypoint inside the app bundle: rejected because they still encode repo assumptions and split orchestration logic across environments.

### 3. Move product state to app-owned directories

The standalone app will use app-owned locations for:
- settings and persisted configuration
- generated project artifacts
- logs and benchmark history
- model and transcript caches
- temporary work files

The repository `generated/` directory remains part of the development workflow, but packaged runs must not depend on it.

Rationale:
- This matches normal desktop-app behavior.
- It avoids mixing product data with a source tree the user may not even have.

Alternatives considered:
- Continue writing to repo-local `generated/`: rejected because a packaged app may not have a writable or meaningful repo root.

### 4. Keep heavyweight AI assets optional and app-managed

The packaged app will support a first-run bootstrap path that prepares required runtime components and downloads optional model assets on demand. Large local AI models should stay outside the signed app payload when practical.

Rationale:
- Shipping every optional model inside the app would create a large and brittle distribution artifact.
- On-demand bootstrap is a better fit for transcript support, CLIP, and optional local VLM runtimes.

Alternatives considered:
- Fully bundle all local models in the app: rejected for size, update cost, and release complexity.

### 5. Preserve dual workflows: packaged product and repo development

The packaged desktop app and the repository development flow will coexist:
- packaged app: app-managed runtime and storage
- repo workflow: npm/scripts for development, debugging, and CI-friendly checks

Rationale:
- The product needs normal desktop distribution.
- The project still needs a developer workflow that is inspectable and hackable.

Alternatives considered:
- Force both modes through one path immediately: rejected because it would over-couple packaging work and development tooling changes.

## Risks / Trade-offs

- [Bundled runtime increases packaging complexity] -> Keep the analyzer as a sidecar instead of rewriting it, and phase the migration around orchestration first.
- [Optional model downloads can fail or confuse users] -> Make first-run bootstrap explicit, visible, retryable, and deterministic-fallback-safe.
- [Packaged and repo workflows may drift] -> Define shared analyzer entrypoints and keep behavior-level specs anchored in OpenSpec.
- [App-managed storage changes output paths] -> Keep artifact formats stable and document the path split between packaged and development workflows.
- [macOS packaging/signing adds release overhead] -> Treat signing, notarization, and installer polish as part of the rollout plan rather than an afterthought.

## Migration Plan

1. Introduce app-managed path resolution and runtime abstraction in the desktop backend.
2. Replace repo-relative shell orchestration in packaged mode with direct desktop-managed invocation.
3. Bundle the analyzer runtime and required binaries as sidecars/resources.
4. Add first-run bootstrap and runtime diagnostics for packaged installs.
5. Add distribution packaging, signing, and release verification for the standalone app.
6. Keep repo-side commands available for development and debugging throughout the rollout.

## Open Questions

- Which runtime components should be bundled in the first packaged release versus downloaded on first use?
- Should packaged benchmark/history artifacts remain user-visible, or move behind an app support directory with export/debug affordances?
- How much of the current shell-script logic should remain as shared internal helpers versus being reimplemented directly in Rust?
