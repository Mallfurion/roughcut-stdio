## ADDED Requirements

### Requirement: Packaged desktop runtime SHALL separate shipped core from optional heavyweight runtimes
The packaged desktop runtime SHALL ship a deterministic/export-capable core by default and SHALL install heavyweight optional runtimes separately rather than bundling all optional capabilities in the initial app payload.

#### Scenario: User launches the packaged app after install
- **WHEN** the user opens the installed packaged app before any optional runtime packs have been downloaded
- **THEN** the app SHALL still launch successfully
- **THEN** the app SHALL still support deterministic processing and Resolve export without requiring those optional packs

### Requirement: Packaged desktop runtime SHALL package a runtime-only Python payload
The packaged desktop runtime SHALL build its embedded Python payload from explicit runtime dependency sets rather than copying the entire local development environment into the app bundle.

#### Scenario: Packaged runtime is staged for release
- **WHEN** the desktop build stages the packaged Python runtime
- **THEN** it SHALL include only runtime dependencies required for the shipped core payload or a declared optional runtime pack
- **THEN** it SHALL exclude development-only environment content that is not required at runtime

### Requirement: Packaged desktop runtime SHALL prune non-runtime Python home content
The packaged desktop runtime SHALL exclude non-runtime Python home content that is not needed for the installed app.

#### Scenario: Python home is bundled for the desktop app
- **WHEN** the packaged build stages Python home content
- **THEN** the build SHALL omit non-runtime assets such as docs, headers, and other unused support content where they are not required for execution
- **THEN** the resulting packaged runtime SHALL remain valid for deterministic processing, export, and installed optional runtime packs
