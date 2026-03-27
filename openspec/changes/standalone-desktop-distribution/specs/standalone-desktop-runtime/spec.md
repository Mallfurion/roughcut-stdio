## ADDED Requirements

### Requirement: Packaged desktop app SHALL run without a repository checkout
The packaged Roughcut Stdio desktop app SHALL support setup, processing, review, and export without requiring the user to have a checked-out repository, repo-relative scripts, or a manually created Python virtual environment.

#### Scenario: User launches an installed app build
- **WHEN** the user opens a packaged desktop build on a supported machine
- **THEN** the app SHALL be able to perform its guided workflow without resolving a repository root
- **THEN** the app SHALL use bundled or app-managed runtime components instead of assuming repo-local developer tooling

### Requirement: Packaged desktop app SHALL use app-managed storage
The packaged Roughcut Stdio desktop app SHALL store settings, generated project artifacts, logs, caches, and runtime state in app-managed directories rather than the repository `generated/` path.

#### Scenario: Packaged app completes a process run
- **WHEN** the user finishes a process run from an installed desktop build
- **THEN** generated project state, diagnostics, and logs SHALL be written under app-managed storage
- **THEN** the run SHALL not depend on a writable source checkout

### Requirement: Packaged desktop app SHALL provide first-run runtime bootstrap
The packaged desktop app SHALL guide the user through first-run runtime preparation for required bundled components and optional downloaded assets while keeping deterministic fallback available.

#### Scenario: Required optional runtime asset is not ready
- **WHEN** transcript support, local AI support, or other optional runtime assets are enabled but not yet prepared
- **THEN** the app SHALL disclose what is missing
- **THEN** the app SHALL provide a first-run bootstrap or download path for that runtime
- **THEN** the app SHALL preserve deterministic or reduced-capability processing when the optional runtime is unavailable
