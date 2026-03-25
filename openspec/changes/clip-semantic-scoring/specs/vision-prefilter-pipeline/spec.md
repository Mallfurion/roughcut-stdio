## MODIFIED Requirements

### Requirement: System SHALL build shortlist candidate regions from screening structure
_No change to this requirement._

### Requirement: System SHALL score sampled visual evidence using cheap, inspectable features
The prefilter stage SHALL include optional CLIP semantic scoring after evidence building and before VLM target selection. When enabled, CLIP scores all shortlisted segments and the `clip_score` field SHALL be included in the prefilter metrics snapshot.

#### Scenario: CLIP is enabled and scoring completes
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and inference succeeds for a segment
- **WHEN** the segment has a contact sheet or keyframe from evidence building
- **THEN** the prefilter metrics snapshot SHALL include a `clip_score` field in [0, 1]
- **THEN** that score SHALL reflect similarity to the fixed editorial prompt set

#### Scenario: CLIP is disabled
- **WHEN** CLIP is not enabled
- **THEN** the prefilter metrics snapshot SHALL not include a `clip_score` field
- **THEN** all other prefilter metrics SHALL be unaffected

### Requirement: System SHALL extract evidence for all shortlisted segments
Evidence building (keyframe extraction and contact sheet creation) SHALL produce contact sheets for all segments in the prefilter shortlist, not just those destined for VLM analysis. This enables CLIP and other semantic layers to operate on a complete set of evidence.

#### Scenario: Evidence building for shortlisted segments
- **WHEN** a segment is in the prefilter shortlist (`prefilter.shortlisted=true`)
- **THEN** its contact sheet and first keyframe SHALL be extracted
- **THEN** these SHALL be available for CLIP scoring and other downstream analysis

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
