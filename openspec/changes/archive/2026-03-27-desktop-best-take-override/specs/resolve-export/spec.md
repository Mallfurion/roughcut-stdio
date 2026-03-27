## MODIFIED Requirements

### Requirement: System SHALL export the generated timeline as `FCPXML`
The system SHALL continue to export the current generated project timeline into an `FCPXML` document for Resolve handoff, but the primary user-facing export flow SHALL be initiated from the desktop app. When desktop review includes best-take overrides, the export action SHALL operate on that active override-resolved timeline state rather than the untouched analyzer baseline.

#### Scenario: User exports from the desktop app
- **WHEN** the user triggers Resolve timeline export from the desktop app after processing
- **THEN** the app SHALL write an `FCPXML` file to the user-selected save location

#### Scenario: Desktop export follows reviewed results
- **WHEN** the desktop review surface shows processed project results
- **THEN** the export action SHALL operate on that active generated project state

#### Scenario: Desktop export follows editor-overridden results
- **WHEN** the desktop review surface shows an active timeline that includes desktop best-take overrides
- **THEN** the export action SHALL use that override-resolved timeline state
- **THEN** the exported `FCPXML` SHALL reflect the same selected takes and ordering shown in desktop review

#### Scenario: Desktop export follows editor-cleared results
- **WHEN** the desktop review surface shows an asset with no active selected take because the editor cleared its best take
- **THEN** the export action SHALL omit that asset from the exported timeline
- **THEN** the exported `FCPXML` SHALL reflect the same reduced or empty timeline shown in desktop review
