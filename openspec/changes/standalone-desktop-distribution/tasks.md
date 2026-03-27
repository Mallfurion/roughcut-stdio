## 1. Runtime Abstraction

- [ ] 1.1 Introduce a desktop runtime abstraction that separates packaged-app paths and runtime commands from repo-development paths.
- [ ] 1.2 Add app-managed directory resolution for settings, generated artifacts, logs, caches, and model storage.
- [ ] 1.3 Update desktop runtime checks to report bundled-runtime readiness separately from optional runtime asset availability.

## 2. Desktop Orchestration

- [ ] 2.1 Replace repo-relative setup/process/export execution in the packaged desktop path with desktop-managed orchestration.
- [ ] 2.2 Preserve the existing npm/script development workflow for repository use without making it the required packaged-app path.
- [ ] 2.3 Ensure packaged process and export commands still emit the generated project, diagnostics, and export artifacts expected by the desktop review flow.

## 3. Bundled Runtime Packaging

- [ ] 3.1 Package the analyzer runtime and required binaries as desktop-app sidecars or bundled resources.
- [ ] 3.2 Define first-run bootstrap behavior for optional transcript and local AI runtime assets.
- [ ] 3.3 Add packaged-build verification for deterministic fallback, transcript-disabled processing, and Resolve export reliability.

## 4. Documentation And Release Readiness

- [ ] 4.1 Update desktop and setup documentation to distinguish packaged-app behavior from repository development behavior.
- [ ] 4.2 Document packaged runtime storage locations, bootstrap behavior, and fallback expectations.
- [ ] 4.3 Add release notes or packaging checklist items for signing, notarization, and standalone-app verification.
