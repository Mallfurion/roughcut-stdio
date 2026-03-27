# review-workspace Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: Web app SHALL load the active generated project for review
The current generated project review capability SHALL be preserved, but the primary review surface for the product SHALL become the desktop application rather than the standalone browser app.

#### Scenario: User completes a desktop process run
- **WHEN** processing completes successfully in the desktop app
- **THEN** the desktop review surface SHALL load the active generated project state for review

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. When a recommended segment was refined, merged, split, or semantically validated before selection, the desktop review surface SHALL display a concise provenance summary for that segment. The frontend implementation of that review surface SHALL isolate project-to-view composition and segment-card rendering behind dedicated review modules instead of the top-level app entrypoint. For each candidate segment, the desktop review surface SHALL combine recommendation outcome with analysis-path details so the editor can see what was analyzed, what was calculated, and why the segment won, lost, or was blocked.

#### Scenario: User opens desktop review after processing
- **WHEN** the generated project contains recommended takes
- **THEN** the desktop UI SHALL display their labels, descriptions, grades, durations, and source metadata
- **THEN** the desktop review rendering path SHALL compose clip and segment presentation through review-focused frontend modules

#### Scenario: Desktop review shows a winning segment
- **WHEN** the generated project contains a segment whose recommendation outcome is the winning take for its asset
- **THEN** the desktop UI SHALL display its recommendation status, total score, technical score, semantic score, story score, and review-facing explanation of why it won

#### Scenario: Desktop review shows a non-winning segment
- **WHEN** the generated project contains a segment that is an alternate or backup rather than the winning take
- **THEN** the desktop UI SHALL display its recommendation status, within-asset rank, score gap to the winner, and explanation of why it did not win

#### Scenario: Desktop review shows analysis-path state
- **WHEN** the generated project contains a candidate segment with screening or analysis status such as shortlist, deduplication, CLIP gate, VLM budget cap, or model-backed evidence
- **THEN** the desktop UI SHALL display a concise analysis-path summary for that segment without requiring the user to inspect process logs

#### Scenario: Recommended segment has refinement provenance
- **WHEN** a recommended segment includes refinement provenance in generated project state
- **THEN** the desktop UI SHALL display its boundary strategy, confidence, lineage summary, and semantic-validation status for editor inspection

#### Scenario: User opens desktop review timeline section
- **WHEN** the generated project contains timeline items
- **THEN** the desktop UI SHALL display their order, trim information, source references, and story summary

### Requirement: Web app SHALL surface AI segment annotations when present
Provider-backed segment understanding and evidence details SHALL remain reviewable, but the primary place they are displayed SHALL become the desktop review workspace.

#### Scenario: Desktop review shows AI understanding
- **WHEN** a candidate segment includes `ai_understanding`
- **THEN** the desktop UI SHALL show provider, keep label, confidence, rationale, and role-oriented details for that segment
