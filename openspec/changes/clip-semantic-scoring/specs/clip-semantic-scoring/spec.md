## ADDED Requirements

### Requirement: System MAY score shortlisted segments against editorial prompts using CLIP
When `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is installed, the analyzer SHALL run CLIP inference on each shortlisted segment's keyframe or contact sheet against a fixed set of positive and negative editorial prompts, producing a `clip_score` in [0, 1] per segment.

#### Scenario: CLIP is enabled and open-clip-torch is available
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is importable
- **THEN** the analyzer SHALL load the CLIP model once at the start of the scoring pass
- **THEN** each shortlisted segment's contact sheet or first keyframe SHALL be scored against the fixed prompt set
- **THEN** `clip_score` SHALL be persisted in the prefilter metrics snapshot for that segment

#### Scenario: CLIP is enabled but open-clip-torch is not installed
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` but `open-clip-torch` cannot be imported
- **THEN** the CLIP scoring pass SHALL be skipped silently
- **THEN** pipeline behavior SHALL be identical to `TIMELINE_AI_CLIP_ENABLED=false`
- **THEN** no error SHALL interrupt the run

#### Scenario: CLIP is disabled
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=false` or the variable is not set
- **THEN** no CLIP model SHALL be loaded
- **THEN** no `clip_score` field SHALL appear in any prefilter metrics snapshot
- **THEN** no `clip_gated` field SHALL be set on any `PrefilterDecision`

### Requirement: System SHALL gate segments below the CLIP threshold away from VLM targeting
When CLIP scoring is active, segments whose `clip_score` falls below `TIMELINE_AI_CLIP_MIN_SCORE` SHALL be excluded from VLM targeting and SHALL receive deterministic understanding instead.

#### Scenario: Segment scores below the CLIP threshold
- **WHEN** a shortlisted segment's `clip_score` is below `TIMELINE_AI_CLIP_MIN_SCORE`
- **THEN** `prefilter.clip_gated` SHALL be set to `True`
- **THEN** the segment SHALL NOT receive keyframe-based VLM analysis
- **THEN** the segment SHALL receive deterministic structured understanding
- **THEN** the segment SHALL remain in `generated/project.json` with its full prefilter record

#### Scenario: Segment scores at or above the CLIP threshold
- **WHEN** a shortlisted segment's `clip_score` is at or above `TIMELINE_AI_CLIP_MIN_SCORE`
- **THEN** `prefilter.clip_gated` SHALL remain `False`
- **THEN** the segment SHALL proceed to VLM targeting as normal

### Requirement: System SHALL enforce a global VLM budget cap
Regardless of whether CLIP is enabled, the total number of VLM targets across all assets SHALL not exceed `TIMELINE_AI_VLM_BUDGET_PCT` percent of the total candidate pool.

#### Scenario: Budget cap is not binding
- **WHEN** the number of VLM-eligible segments after deduplication and CLIP gating is at or below the budget cap
- **THEN** all eligible segments SHALL proceed to VLM targeting
- **THEN** `vlm_budget_was_binding` SHALL be `False` in the analysis summary

#### Scenario: Budget cap is binding
- **WHEN** the number of VLM-eligible segments exceeds the budget cap
- **THEN** segments SHALL be ranked across all assets by composite prefilter and CLIP score
- **THEN** the lowest-scoring segments above the cap SHALL be marked `prefilter.vlm_budget_capped=True`
- **THEN** those segments SHALL receive deterministic understanding and SHALL NOT receive VLM analysis
- **THEN** `vlm_budget_was_binding` SHALL be `True` in the analysis summary

#### Scenario: Budget cap is set to zero or disabled
- **WHEN** `TIMELINE_AI_VLM_BUDGET_PCT` is set to `0`
- **THEN** no segments SHALL reach VLM targeting and all SHALL receive deterministic understanding
