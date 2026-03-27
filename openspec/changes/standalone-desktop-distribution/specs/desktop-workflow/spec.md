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
The desktop app SHALL surface whether required packaged runtime components are ready for processing and SHALL distinguish bundled readiness from optional runtime downloads or unavailable AI features.

#### Scenario: User reviews runtime health in a packaged build
- **WHEN** the desktop app checks runtime status in an installed build
- **THEN** it SHALL disclose whether the packaged processing runtime is ready
- **THEN** it SHALL distinguish optional runtime features that still need bootstrap or download
- **THEN** the user SHALL still be able to proceed with supported fallback modes
