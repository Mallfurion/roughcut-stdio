## ADDED Requirements

### Requirement: Desktop app SHALL persist editor take overrides in the local review workflow
The desktop app SHALL let the user persist best-take editorial state for an asset during desktop review, including selecting a different active take or explicitly clearing the active take, and SHALL reuse that state when loading the active project until the user clears it or a different generated project replaces the current one.

#### Scenario: User promotes a segment to the active best take
- **WHEN** the user marks a candidate segment as the best take for its asset in desktop review
- **THEN** the desktop app SHALL persist that override locally for the active generated project
- **THEN** subsequent desktop reloads of that same generated project SHALL preserve the override-resolved selection state

#### Scenario: User clears an existing best-take override
- **WHEN** the user clears a previously stored best-take override for an asset
- **THEN** the desktop app SHALL remove the local override for that asset
- **THEN** the active selection state for that asset SHALL fall back to the analyzer-selected take set

#### Scenario: User clears the active best take for an asset
- **WHEN** the user clears the currently selected best take for an asset in desktop review
- **THEN** the desktop app SHALL persist that cleared-selection state locally for the active generated project
- **THEN** the active resolved project state SHALL contain no selected take for that asset until the editor restores analyzer state or promotes another segment

#### Scenario: Stored override does not match the current generated project
- **WHEN** the desktop app loads a generated project whose identity or candidate segment set no longer matches a stored override entry
- **THEN** the app SHALL ignore that incompatible override entry
- **THEN** the active review state SHALL continue from the generated project without applying stale editorial state
