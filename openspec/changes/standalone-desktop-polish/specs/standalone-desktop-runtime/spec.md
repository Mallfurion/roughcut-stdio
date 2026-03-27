## ADDED Requirements

### Requirement: Packaged desktop runtime SHALL support runtime repair after install
The packaged desktop runtime SHALL support repair, re-check, and targeted asset re-download actions after installation without requiring a repository checkout or manual terminal workflow.

#### Scenario: Installed runtime needs repair
- **WHEN** the user triggers a packaged runtime repair action after installation
- **THEN** the app SHALL re-run the relevant packaged runtime setup/bootstrap logic for the requested runtime scope
- **THEN** the app SHALL preserve deterministic or reduced-capability fallback when optional runtime assets remain unavailable

### Requirement: Packaged desktop runtime SHALL support explicit repo-state import
The packaged desktop runtime SHALL support importing compatible repo-local settings and generated artifacts into app-managed packaged storage as a non-destructive operation.

#### Scenario: Packaged app imports repo-local state
- **WHEN** the user imports compatible repo-local settings or generated artifacts into packaged storage
- **THEN** the app SHALL copy or translate the imported state into packaged storage
- **THEN** the app SHALL leave the original repo-local files unchanged

### Requirement: Packaged release packaging SHALL be CI-safe and reliable
The packaged desktop release process SHALL produce a valid app bundle without depending on Finder-driven DMG layout automation, and any DMG generation path used for automation SHALL be non-interactive and CI-safe by default.

#### Scenario: Automated packaged release build runs
- **WHEN** the desktop release build runs in an automated or non-interactive environment
- **THEN** the `.app` bundle SHALL remain a valid primary build artifact
- **THEN** DMG generation SHALL not depend on Finder interaction or cosmetic layout steps that can fail after the app bundle is already built
