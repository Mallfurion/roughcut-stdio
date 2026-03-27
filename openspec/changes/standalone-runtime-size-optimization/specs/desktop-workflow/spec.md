## ADDED Requirements

### Requirement: Desktop app SHALL distinguish installed core runtime from optional packs
The packaged desktop workflow SHALL distinguish the runtime shipped in the initial install from optional downloadable runtime packs.

#### Scenario: User reviews packaged runtime state
- **WHEN** the packaged desktop app shows runtime readiness or setup state
- **THEN** it SHALL identify which capabilities are available from the installed core payload
- **THEN** it SHALL identify which capabilities require an optional runtime pack download

### Requirement: Desktop app SHALL guide the user through optional pack installation
The packaged desktop workflow SHALL provide an explicit install path for optional runtime packs when the user requests a capability that is not part of the installed core payload.

#### Scenario: Requested capability needs an optional runtime pack
- **WHEN** the user selects a workflow or setting that depends on an uninstalled optional runtime pack
- **THEN** the app SHALL explain which pack is missing
- **THEN** the app SHALL offer an installation or download action for that pack before entering the requested capability
