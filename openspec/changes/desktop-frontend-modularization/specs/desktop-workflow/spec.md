## MODIFIED Requirements

### Requirement: Desktop app SHALL provide a guided local workflow
The product SHALL provide a Tauri-based desktop workflow for the local Mac usage model instead of relying on terminal-first and browser-first interaction as the primary user experience. The frontend implementation of that workflow SHALL be organized behind explicit modules for bootstrap, state, platform access, and step rendering rather than being centralized in one entrypoint file.

#### Scenario: User opens the desktop app
- **WHEN** the desktop app starts
- **THEN** it SHALL provide a guided workflow for runtime choice, setup, media selection, processing, review, and export
- **THEN** the app bootstrap path SHALL delegate workflow initialization and rendering responsibilities through dedicated frontend modules
