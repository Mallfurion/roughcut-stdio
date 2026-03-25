## MODIFIED Requirements

### Requirement: System SHALL build shortlist candidate regions from screening structure
_No change to this requirement._

### Requirement: System SHALL score sampled visual evidence using cheap, inspectable features
When CLIP is enabled, the prefilter stage SHALL include CLIP semantic scoring as an optional final step after visual and audio signal aggregation. The `clip_score` field SHALL be included in the prefilter metrics snapshot when CLIP is active.

#### Scenario: CLIP is enabled and scoring completes
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and inference succeeds for a segment
- **THEN** the prefilter metrics snapshot SHALL include a `clip_score` field in [0, 1]
- **THEN** that score SHALL reflect similarity to the fixed editorial prompt set

#### Scenario: CLIP is disabled
- **WHEN** CLIP is not enabled
- **THEN** the prefilter metrics snapshot SHALL not include a `clip_score` field
- **THEN** all other prefilter metrics SHALL be unaffected

### Requirement: System SHALL persist prefilter outputs for inspection and reuse
The prefilter record for each segment SHALL include `clip_gated` and `vlm_budget_capped` fields when applicable, so the reason a segment did not reach VLM targeting is always explicit.

#### Scenario: Segment is excluded by the CLIP gate
- **WHEN** `clip_score` is below `TIMELINE_AI_CLIP_MIN_SCORE`
- **THEN** `PrefilterDecision.clip_gated` SHALL be `True`
- **THEN** the selection reason SHALL name the CLIP gate as the exclusion cause

#### Scenario: Segment is excluded by the global VLM budget cap
- **WHEN** a segment is VLM-eligible after CLIP gating but falls outside the global budget
- **THEN** `PrefilterDecision.vlm_budget_capped` SHALL be `True`
- **THEN** the selection reason SHALL name the budget cap as the exclusion cause
