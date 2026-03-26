## MODIFIED Requirements

### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing. When semantic boundary validation runs on an ambiguous segment, the analyzer SHALL also persist the boundary decision, decision reason, validation status, and impact metadata for that segment.

#### Scenario: Semantic boundary validation changes a segment
- **WHEN** semantic boundary validation trims, extends, or splits a segment
- **THEN** the generated project SHALL persist the validation impact alongside the segment provenance
- **THEN** downstream review SHALL be able to distinguish a no-op validation from a materially changed boundary
