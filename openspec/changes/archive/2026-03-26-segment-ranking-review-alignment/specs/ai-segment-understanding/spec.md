## MODIFIED Requirements

### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing. The persisted segment state SHALL also remain reviewable enough to distinguish whether a segment was shortlisted, keyframed, CLIP scored or gated, deduplicated, VLM analyzed, budget-capped, or carried forward by deterministic fallback.

#### Scenario: Candidate segment is analyzed with model-backed evidence
- **WHEN** the analyzer finishes model-backed processing for a shortlisted candidate segment
- **THEN** the generated project SHALL contain a persisted evidence bundle for that segment
- **THEN** the generated project SHALL contain a persisted segment-understanding record for that segment
- **THEN** the generated project SHALL make its analysis path reviewable as a model-analyzed segment

#### Scenario: Candidate segment is skipped before model analysis
- **WHEN** a candidate segment is not sent to a model because of shortlisting, deduplication, CLIP gating, or budget capping
- **THEN** the generated project SHALL still make that segment's analysis path reviewable
- **THEN** the persisted state SHALL distinguish deterministic fallback from model-backed analysis
