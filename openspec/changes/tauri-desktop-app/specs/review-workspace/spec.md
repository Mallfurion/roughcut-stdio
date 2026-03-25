# review-workspace Specification

## MODIFIED Requirements

### Requirement: Web app SHALL load the active generated project for review
The current generated project review capability SHALL be preserved, but the primary review surface for the product SHALL become the desktop application rather than the standalone browser app.

#### Scenario: User completes a desktop process run
- **WHEN** processing completes successfully in the desktop app
- **THEN** the desktop review surface SHALL load the active generated project state for review

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface.

#### Scenario: User opens desktop review after processing
- **WHEN** the generated project contains recommended takes
- **THEN** the desktop UI SHALL display their labels, descriptions, grades, durations, and source metadata

#### Scenario: User opens desktop review timeline section
- **WHEN** the generated project contains timeline items
- **THEN** the desktop UI SHALL display their order, trim information, source references, and story summary

### Requirement: Web app SHALL surface AI segment annotations when present
Provider-backed segment understanding and evidence details SHALL remain reviewable, but the primary place they are displayed SHALL become the desktop review workspace.

#### Scenario: Desktop review shows AI understanding
- **WHEN** a candidate segment includes `ai_understanding`
- **THEN** the desktop UI SHALL show provider, keep label, confidence, rationale, and role-oriented details for that segment
