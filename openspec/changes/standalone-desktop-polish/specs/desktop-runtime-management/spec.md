## ADDED Requirements

### Requirement: Packaged desktop app SHALL expose runtime management
The packaged desktop app SHALL provide a runtime-management surface that lets the user inspect bundled runtime readiness, downloaded asset readiness, configured runtime mode, and runtime storage state without leaving the app.

#### Scenario: User opens runtime management
- **WHEN** the user opens the runtime-management surface from an installed desktop build
- **THEN** the app SHALL display bundled runtime readiness
- **THEN** the app SHALL display model-asset readiness for the current packaged workflow
- **THEN** the app SHALL display the configured AI/transcript runtime mode and app-managed storage locations

### Requirement: Packaged desktop app SHALL support runtime repair actions
The packaged desktop app SHALL let the user re-check, repair, or re-download packaged runtime assets from the runtime-management surface.

#### Scenario: User repairs packaged runtime assets
- **WHEN** the user triggers a repair or re-download action for packaged runtime assets
- **THEN** the app SHALL run packaged setup/bootstrap orchestration for the requested runtime scope
- **THEN** the app SHALL report whether the repair succeeded, failed, or still requires fallback

### Requirement: Packaged desktop app SHALL support repo-state import
The packaged desktop app SHALL support importing compatible repo-local settings and generated-state artifacts into app-managed packaged storage.

#### Scenario: User imports repo-local state
- **WHEN** the user triggers repo-state import from a packaged build
- **THEN** the app SHALL import compatible repo settings into packaged configuration storage
- **THEN** the app SHALL import compatible generated run artifacts into packaged run storage
- **THEN** the app SHALL report imported items and skipped items without mutating the original repo-local files
