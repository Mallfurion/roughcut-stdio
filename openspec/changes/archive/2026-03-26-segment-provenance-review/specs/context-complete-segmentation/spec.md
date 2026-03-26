## MODIFIED Requirements

### Requirement: System SHALL persist deterministic boundary provenance
Each deterministically refined candidate segment SHALL persist the strategy and confidence used to form its boundaries. When a final candidate segment is produced through merge, split, or semantic validation operations, the analyzer SHALL additionally persist the source lineage, assembly rule family, and semantic-validation status needed for review and downstream inspection.

#### Scenario: Final segment is written to generated project state
- **WHEN** processing completes successfully for a final candidate segment
- **THEN** the generated project SHALL include review-facing provenance for that segment, including boundary strategy, confidence, lineage summary, and semantic-validation status
