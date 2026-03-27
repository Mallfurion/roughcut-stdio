## MODIFIED Requirements

### Requirement: Repository SHALL expose an npm-first workflow
The repository workflow SHALL continue to support preparing and validating the configured AI backend through npm-first commands for development and debugging, but the primary product workflow SHALL move to desktop-managed orchestration. The packaged desktop app SHALL execute setup, processing, and export through app-managed orchestration rather than relying on repo-relative shell scripts.

#### Scenario: Desktop app performs setup
- **WHEN** the desktop app prepares the local environment
- **THEN** it SHALL use the same underlying setup capabilities as the repository workflow without requiring the user to run npm commands manually
- **THEN** a packaged build SHALL invoke app-managed runtime setup rather than repo-relative shell scripts as its required execution path

#### Scenario: Desktop app starts a process run
- **WHEN** the desktop app launches a process run
- **THEN** the analyzer SHALL execute under desktop orchestration rather than requiring terminal-first interaction
- **THEN** a packaged build SHALL use bundled or app-managed runtime components instead of assuming a repo `.venv`

## ADDED Requirements

### Requirement: Packaged process workflow SHALL preserve generated artifacts and diagnostics
The packaged desktop workflow SHALL preserve the same project-level generated state, processing diagnostics, benchmark artifacts, and export-oriented artifacts that the repository workflow exposes, even when those artifacts are written to app-managed storage.

#### Scenario: Packaged process run completes
- **WHEN** the user completes a process run from an installed desktop build
- **THEN** the app SHALL persist a generated project document, process diagnostics, benchmark history, and exportable timeline state
- **THEN** those artifacts SHALL remain inspectable to the desktop workflow even if their storage location differs from the repository `generated/` path

### Requirement: Packaged process workflow SHALL translate packaged settings into runtime configuration
The packaged desktop workflow SHALL persist packaged settings outside repo `.env` files and SHALL translate those settings into analyzer/runtime configuration when packaged commands execute.

#### Scenario: Packaged app runs with saved settings
- **WHEN** the user saves runtime settings in an installed desktop build
- **THEN** the app SHALL persist those settings in app-managed configuration storage
- **THEN** a subsequent packaged process or export run SHALL use those persisted settings without requiring a repository `.env` file
