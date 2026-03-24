# review-workspace Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: Web app SHALL load the active generated project for review
The review application SHALL load the latest generated project state when present and SHALL fall back to the sample fixture only when generated project data is not available.

#### Scenario: Generated project exists
- **WHEN** `generated/project.json` is present
- **THEN** the web app SHALL present that generated project as the active review source

#### Scenario: Generated project does not exist
- **WHEN** the user opens the web app before running the pipeline
- **THEN** the web app MAY fall back to the bundled sample fixture state

### Requirement: Web app SHALL expose recommended segments and timeline state
The review application SHALL show recommended takes, segment descriptions, scoring context, asset metadata, and the rough timeline built from the generated project state.

#### Scenario: User opens the take review surface
- **WHEN** the generated project contains recommended takes
- **THEN** the UI SHALL display their labels, descriptions, durations, and source metadata

#### Scenario: User opens the timeline section
- **WHEN** the generated project contains timeline items
- **THEN** the UI SHALL display their order, trim information, source references, and story summary

### Requirement: Web app SHALL surface AI segment annotations when present
The review application SHALL display provider-backed segment understanding and evidence details when the generated project includes them.

#### Scenario: Segment contains AI understanding
- **WHEN** a candidate segment includes `ai_understanding`
- **THEN** the UI SHALL show provider, keep label, confidence, rationale, and role-oriented details for that segment

#### Scenario: Segment contains evidence bundle data
- **WHEN** a candidate segment includes `evidence_bundle`
- **THEN** the UI SHALL show keyframe coverage and segment context-window details

