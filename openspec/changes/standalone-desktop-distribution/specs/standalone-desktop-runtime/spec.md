## ADDED Requirements

### Requirement: Packaged desktop app SHALL run without a repository checkout
The packaged Roughcut Stdio desktop app SHALL support setup, processing, review, and export without requiring the user to have a checked-out repository, repo-relative scripts, or a manually created Python virtual environment.

#### Scenario: User launches an installed app build
- **WHEN** the user opens a packaged desktop build on a supported machine
- **THEN** the app SHALL be able to perform its guided workflow without resolving a repository root
- **THEN** the app SHALL use bundled or app-managed runtime components instead of assuming repo-local developer tooling

### Requirement: Packaged desktop app SHALL bundle the core processing runtime
The packaged Roughcut Stdio desktop app SHALL include the core runtime dependencies required for normal processing, including the Python runtime, analyzer environment, `ffmpeg`, `ffprobe`, and export helpers, so the installed build can run deterministic processing immediately after installation.

#### Scenario: User runs a packaged app offline after install
- **WHEN** the user opens an installed packaged build without network access
- **THEN** the app SHALL still launch and complete supported deterministic processing without depending on host Python, Homebrew-installed media tools, or a repository checkout

### Requirement: Packaged desktop app SHALL use app-managed storage
The packaged Roughcut Stdio desktop app SHALL store settings, generated project artifacts, logs, caches, and runtime state in app-managed directories rather than the repository `generated/` path.

#### Scenario: Packaged app completes a process run
- **WHEN** the user finishes a process run from an installed desktop build
- **THEN** generated project state, diagnostics, logs, and benchmark artifacts SHALL be written under app-managed storage
- **THEN** the run SHALL not depend on a writable source checkout

### Requirement: Packaged desktop app SHALL persist settings outside repo env files
The packaged Roughcut Stdio desktop app SHALL persist its runtime settings outside repository `.env` files while preserving equivalent runtime configuration semantics for analyzer execution.

#### Scenario: Packaged user saves settings
- **WHEN** the user updates AI, transcript, or processing settings in an installed build
- **THEN** the app SHALL persist those settings in app-managed configuration storage
- **THEN** a later packaged run SHALL use those settings without reading or writing repository `.env` files

### Requirement: Packaged desktop app SHALL provide first-run runtime bootstrap
The packaged desktop app SHALL guide the user through first-run runtime preparation for required model assets and optional downloaded assets while keeping deterministic fallback available where supported.

#### Scenario: Required packaged model assets are not ready
- **WHEN** the configured packaged workflow depends on model assets that are not yet prepared
- **THEN** the app SHALL disclose what is missing
- **THEN** the app SHALL provide a startup bootstrap or download path for those assets
- **THEN** downloaded assets SHALL be stored in app-managed storage outside the signed app bundle

#### Scenario: Optional runtime asset is unavailable
- **WHEN** transcript support, provider-specific local AI support, or other optional runtime assets are enabled but not yet prepared
- **THEN** the app SHALL disclose what is missing
- **THEN** the app SHALL provide a bootstrap or download path for that runtime
- **THEN** the app SHALL preserve deterministic or reduced-capability processing when the optional runtime is unavailable and the selected workflow supports fallback
