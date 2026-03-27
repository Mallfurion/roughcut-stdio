## 1. Runtime Abstraction

- [ ] 1.1 Introduce a desktop runtime abstraction with distinct packaged-app and repo-development backends.
- [ ] 1.2 Add app-managed directory resolution for packaged settings, generated artifacts, logs, caches, model storage, and temporary work files.
- [ ] 1.3 Keep repo-development path resolution and `.env`-based configuration working for local development and debugging.
- [ ] 1.4 Update desktop runtime checks to report bundled runtime readiness separately from model-asset readiness.

## 2. Packaged Configuration And Storage

- [ ] 2.1 Move packaged desktop settings persistence from repo `.env` files to app-managed configuration storage.
- [ ] 2.2 Translate packaged settings into analyzer environment variables only at command execution time.
- [ ] 2.3 Write packaged generated project state, logs, summaries, and benchmark artifacts under app-managed storage while preserving the artifact formats expected by the review/export flow.
- [ ] 2.4 Scope packaged review loading to the active/latest generated run for v1.

## 3. Desktop Orchestration

- [ ] 3.1 Replace packaged setup/runtime-check/process/export execution with desktop-managed orchestration over the runtime abstraction.
- [ ] 3.2 Preserve the existing repo script workflow for development mode without making it the required packaged-app path.
- [ ] 3.3 Ensure packaged process and export commands still emit the generated project, diagnostics, benchmark history, and export artifacts expected by the desktop review flow.

## 4. Bundled Runtime Packaging

- [ ] 4.1 Bundle the Python runtime, analyzer environment, `ffmpeg`, `ffprobe`, and export helpers as packaged resources or sidecars.
- [ ] 4.2 Ensure the installed packaged app can launch and run deterministic processing without host Python, Homebrew, or a checked-out repository.
- [ ] 4.3 Add packaged-build verification for deterministic fallback, transcript-disabled processing, and Resolve export reliability.

## 5. Model Bootstrap

- [ ] 5.1 Define the packaged default workflow asset set, including first-run CLIP and default transcript assets.
- [ ] 5.2 Define optional/provider-specific assets, including MLX-VLM model downloads when that provider is enabled.
- [ ] 5.3 Add a startup bootstrap screen that detects missing required model assets and offers a download action before entering the full workflow.
- [ ] 5.4 Store downloaded model assets in app-managed storage outside the signed app bundle.
- [ ] 5.5 Add retry/recheck behavior and a reduced-capability fallback path when optional assets are unavailable or skipped.

## 6. Documentation And Release Readiness

- [ ] 6.1 Update desktop and setup documentation to distinguish packaged-app behavior from repository development behavior.
- [ ] 6.2 Document packaged runtime storage locations, startup bootstrap behavior, required vs optional assets, and fallback expectations.
- [ ] 6.3 Add release notes or packaging checklist items for signing, notarization, bundled-runtime verification, and first-run bootstrap verification.
