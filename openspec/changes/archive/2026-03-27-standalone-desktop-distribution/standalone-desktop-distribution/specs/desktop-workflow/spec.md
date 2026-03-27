## MODIFIED Requirements

### Requirement: Desktop app SHALL provide a guided local workflow
The product SHALL provide a Tauri-based desktop workflow for the local Mac usage model instead of relying on terminal-first and browser-first interaction as the primary user experience. The frontend implementation of that workflow SHALL be organized behind explicit modules for bootstrap, state, platform access, and step rendering rather than being centralized in one entrypoint file. The packaged desktop app SHALL preserve that guided workflow without requiring a checked-out repository or manual terminal-first setup.

#### Scenario: User opens the desktop app
- **WHEN** the desktop app starts
- **THEN** it SHALL provide a guided workflow for runtime choice, setup, media selection, processing, review, and export
- **THEN** the app bootstrap path SHALL delegate workflow initialization and rendering responsibilities through dedicated frontend modules
- **THEN** a packaged build SHALL not require the user to run repo setup commands manually before entering that workflow

## ADDED Requirements

### Requirement: Desktop app SHALL expose packaged-runtime readiness
The desktop app SHALL surface whether required packaged runtime components are ready for processing and SHALL distinguish bundled runtime readiness from model-asset readiness or unavailable optional AI features.

#### Scenario: User reviews runtime health in a packaged build
- **WHEN** the desktop app checks runtime status in an installed build
- **THEN** it SHALL disclose whether the bundled packaged processing runtime is ready
- **THEN** it SHALL distinguish missing required model assets from optional runtime features that still need bootstrap or download
- **THEN** the user SHALL still be able to proceed with supported fallback modes when only optional assets are unavailable

### Requirement: Desktop app SHALL provide a startup bootstrap screen for missing model assets
The packaged desktop app SHALL check model readiness during startup and SHALL present a dedicated bootstrap screen when assets required for the currently configured packaged workflow are missing.

#### Scenario: Required packaged model asset is missing
- **WHEN** the packaged app starts and required model assets are not yet present in app-managed storage
- **THEN** it SHALL show a bootstrap screen before entering the full workflow
- **THEN** that screen SHALL describe which assets are missing and why they are needed
- **THEN** the user SHALL be able to trigger a download/retry action from that screen
- **THEN** the app SHALL re-check readiness after the download completes
