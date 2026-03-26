## MODIFIED Requirements

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. When a recommended segment was refined, merged, split, or semantically validated before selection, the desktop review surface SHALL display a concise provenance summary for that segment.

#### Scenario: User opens desktop review after processing
- **WHEN** the generated project contains recommended takes
- **THEN** the desktop UI SHALL display their labels, descriptions, grades, durations, and source metadata

#### Scenario: Recommended segment has refinement provenance
- **WHEN** a recommended segment includes refinement provenance in generated project state
- **THEN** the desktop UI SHALL display its boundary strategy, confidence, lineage summary, and semantic-validation status for editor inspection

#### Scenario: User opens desktop review timeline section
- **WHEN** the generated project contains timeline items
- **THEN** the desktop UI SHALL display their order, trim information, source references, and story summary
