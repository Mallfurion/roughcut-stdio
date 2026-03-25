# resolve-export Specification

## MODIFIED Requirements

### Requirement: System SHALL export the generated timeline as `FCPXML`
The system SHALL continue to export the current generated project timeline into an `FCPXML` document for Resolve handoff, but the primary user-facing export flow SHALL be initiated from the desktop app.

#### Scenario: User exports from the desktop app
- **WHEN** the user triggers Resolve timeline export from the desktop app after processing
- **THEN** the app SHALL write an `FCPXML` file to the user-selected save location

#### Scenario: Desktop export follows reviewed results
- **WHEN** the desktop review surface shows processed project results
- **THEN** the export action SHALL operate on that active generated project state
