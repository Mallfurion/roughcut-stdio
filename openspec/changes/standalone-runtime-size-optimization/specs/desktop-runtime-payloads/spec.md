## ADDED Requirements

### Requirement: Packaged desktop app SHALL define a slim core runtime payload
The packaged desktop app SHALL ship a core runtime payload that is sufficient for deterministic processing, generated artifact writing, media probing, and Resolve export without bundling every optional AI-related dependency in the initial install.

#### Scenario: User installs the packaged app
- **WHEN** the user installs the packaged desktop app
- **THEN** the initial install SHALL include the runtime needed for deterministic processing and Resolve export
- **THEN** the initial install SHALL not require optional transcript, CLIP, or MLX-VLM runtime packs to launch or run deterministic processing

### Requirement: Packaged desktop app SHALL support optional runtime packs
The packaged desktop app SHALL define optional downloadable runtime packs for heavyweight capabilities that are not required for deterministic core processing.

#### Scenario: User enables a heavyweight optional capability
- **WHEN** the user enables transcript, CLIP, or MLX-VLM functionality that is not part of the installed core payload
- **THEN** the app SHALL identify the required runtime pack
- **THEN** the app SHALL offer an install or download path for that runtime pack before attempting the requested capability

### Requirement: Release verification SHALL enforce payload budgets
The packaged desktop build SHALL report core payload size, optional pack sizes, and the largest packaged dependencies, and SHALL support budget-based verification for release builds.

#### Scenario: Release verification runs
- **WHEN** the packaged runtime verification or release packaging checks run
- **THEN** they SHALL report core bundle size and optional pack sizes
- **THEN** they SHALL fail or warn when configured payload budgets are exceeded
