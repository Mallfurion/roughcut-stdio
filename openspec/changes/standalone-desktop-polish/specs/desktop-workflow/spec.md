## ADDED Requirements

### Requirement: Desktop app SHALL offer first-launch packaged import
The packaged desktop workflow SHALL offer an explicit first-launch import path when compatible repo-local settings or generated state are detected.

#### Scenario: First packaged launch detects repo-local state
- **WHEN** the user opens a packaged desktop build and compatible repo-local settings or generated artifacts are discoverable
- **THEN** the app SHALL offer an explicit import option before the user starts a new packaged workflow
- **THEN** the app SHALL let the user skip import and continue with packaged defaults

### Requirement: Desktop app SHALL provide access to runtime management and run history
The packaged desktop workflow SHALL provide visible entrypoints to runtime management and packaged run history after first launch.

#### Scenario: User needs maintenance or prior-run access
- **WHEN** the user is in the packaged desktop workflow after startup
- **THEN** the app SHALL provide a way to open runtime management without waiting for startup blocking state
- **THEN** the app SHALL provide a way to open packaged run history without requiring a new process run
