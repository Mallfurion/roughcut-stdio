## MODIFIED Requirements

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. The desktop review surface SHALL also let the editor promote a candidate segment to the active best take for its asset, clear the active best take for an asset, SHALL refresh the active timeline state to reflect that editorial state, and SHALL display concise sequence-level rationale and override state for editor inspection.

#### Scenario: Timeline item has story-assembly rationale
- **WHEN** a recommended timeline item includes project-level sequence rationale in generated project state
- **THEN** the desktop UI SHALL display that rationale for editor inspection

#### Scenario: User promotes a non-selected segment from desktop review
- **WHEN** the generated project contains a candidate segment that is not currently the active selected take for its asset
- **THEN** the desktop UI SHALL offer an action to mark that segment as the active best take
- **THEN** the desktop review surface SHALL refresh to show that segment as selected and the previous selected segment from that asset as no longer active

#### Scenario: Active selection came from an editor override
- **WHEN** the active selected take for an asset comes from a desktop override instead of the analyzer default
- **THEN** the desktop review surface SHALL show that the take is editor-overridden
- **THEN** the desktop review surface SHALL offer a clear action to restore analyzer-selected state for that asset

#### Scenario: Editor clears the active best take for an asset
- **WHEN** the editor clears the currently selected best take for an asset
- **THEN** the desktop review surface SHALL remove that asset from the active timeline preview
- **THEN** the review surface SHALL show that the previously selected analyzer take was cleared from the timeline
- **THEN** the editor SHALL still be able to promote another candidate segment for that asset
