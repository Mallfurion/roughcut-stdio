## 1. Migration And Runtime Metadata

- [ ] 1.1 Add packaged run manifest and run-index persistence for packaged process runs.
- [ ] 1.2 Add backend commands to list packaged runs and load a selected run by run id.
- [ ] 1.3 Add backend commands to detect compatible repo-local settings/generated state and import them into packaged storage.

## 2. Desktop Workflow Updates

- [ ] 2.1 Add a first-launch packaged import prompt when compatible repo-local state is detected.
- [ ] 2.2 Add packaged run-history navigation in the desktop workflow.
- [ ] 2.3 Update review loading so the desktop app can open a selected historical packaged run.

## 3. Runtime Management

- [ ] 3.1 Add a runtime-management surface that shows bundled runtime health, asset readiness, configured runtime mode, and storage locations.
- [ ] 3.2 Add runtime-management actions for re-check, repair, and targeted asset re-download.
- [ ] 3.3 Report import results and skipped items clearly in the runtime-management or first-launch import flow.

## 4. Packaging Reliability

- [ ] 4.1 Harden the desktop release build so `.app` output remains the primary success artifact.
- [ ] 4.2 Make DMG generation CI-safe and non-interactive by default for automated packaging.
- [ ] 4.3 Extend packaged verification to cover import, historical-run reopening, and repaired-runtime flows.

## 5. Documentation

- [ ] 5.1 Document packaged import, runtime management, and run-library behavior.
- [ ] 5.2 Document the updated release packaging path and DMG reliability expectations.
