## ADDED Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis.

#### Scenario: Deterministic structure is available for refinement
- **WHEN** a seed region overlaps transcript spans, audio transitions, scene boundaries, or other local boundary cues
- **THEN** the analyzer SHALL use those cues to snap, extend, or trim the seed region
- **THEN** the refined region SHALL become the candidate segment passed downstream

#### Scenario: Deterministic structure is limited
- **WHEN** a seed region lacks transcript, audio, or scene cues
- **THEN** the analyzer SHALL still produce a bounded refined candidate segment using heuristic fallback rules
- **THEN** processing SHALL continue without requiring AI assistance

### Requirement: System SHALL persist deterministic boundary provenance
Each deterministically refined candidate segment SHALL persist the strategy and confidence used to form its boundaries.

#### Scenario: Refined segment is written to generated project state
- **WHEN** processing completes successfully
- **THEN** each refined candidate segment SHALL include its boundary strategy, boundary confidence, and source seed provenance
