## MODIFIED Requirements

### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing. When semantic boundary validation runs on an ambiguous segment, the analyzer SHALL also persist the boundary decision, decision reason, and validation status for that segment.

#### Scenario: Candidate segment is analyzed
- **WHEN** the analyzer finishes processing a candidate segment
- **THEN** the generated project SHALL contain a persisted evidence bundle for that segment
- **THEN** the generated project SHALL contain a persisted segment-understanding record for that segment

#### Scenario: Semantic boundary validation runs
- **WHEN** the analyzer performs semantic boundary validation on an ambiguous segment
- **THEN** the generated project SHALL persist the validation result and validation status for that segment

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
The analyzer SHALL use expensive multimodal analysis only after prefilter shortlist construction, regardless of whether the configured provider is `lmstudio` or `mlx-vlm-local`. Optional semantic boundary validation SHALL remain separately controllable, SHALL run only on eligible ambiguous segments within explicit runtime limits, and SHALL preserve deterministic fallback when it does not run.

#### Scenario: Boundary validation budget is capped
- **WHEN** semantic boundary validation is enabled with a configured runtime limit
- **THEN** the analyzer SHALL validate only the eligible ambiguous subset that fits within that limit
- **THEN** all remaining segments SHALL keep deterministic output and persisted skip metadata
