## MODIFIED Requirements

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
In addition to per-asset shortlist controls and fast mode, the analyzer SHALL enforce a global VLM budget cap that limits total VLM targets to a configured percentage of all candidates. This cap SHALL apply after deduplication and CLIP gating and SHALL be the final gate before VLM invocation.

#### Scenario: Global budget cap is configured and binding
- **WHEN** `TIMELINE_AI_VLM_BUDGET_PCT` is set and the number of eligible segments exceeds the budget
- **THEN** only the top-scoring eligible segments up to the budget limit SHALL receive VLM analysis
- **THEN** segments excluded by the budget cap SHALL receive deterministic structured understanding
- **THEN** `prefilter.vlm_budget_capped=True` SHALL be set on each excluded segment

#### Scenario: Segment is gated by CLIP before reaching VLM
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and a segment's `clip_score` is below `TIMELINE_AI_CLIP_MIN_SCORE`
- **THEN** that segment SHALL NOT reach the VLM stage
- **THEN** its structured understanding SHALL indicate that it was gated by CLIP semantic scoring
- **THEN** it SHALL still receive deterministic structured understanding

### Requirement: Process SHALL expose AI runtime behavior to the user
Process reporting SHALL include CLIP and VLM budget statistics alongside existing provider, mode, and cache reporting.

#### Scenario: CLIP is enabled during a process run
- **WHEN** `npm run process` completes with `TIMELINE_AI_CLIP_ENABLED=true`
- **THEN** the process output SHALL report the number of segments scored by CLIP, the number gated by CLIP, and the CLIP model used

#### Scenario: Global budget cap is binding during a process run
- **WHEN** `npm run process` completes and the VLM budget cap was reached
- **THEN** the process output SHALL indicate that the cap was binding, report the effective VLM target count, and report VLM targets as a percentage of total candidates
