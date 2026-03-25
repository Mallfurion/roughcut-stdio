## MODIFIED Requirements

### Requirement: System SHALL build shortlist candidate regions from screening structure
The prefilter pipeline SHALL include a deduplication step as a named stage between prefilter scoring and shortlist selection. The shortlist SHALL be selected from the deduplicated candidate set, not the full candidate set.

#### Scenario: Deduplication eliminates candidates before shortlist selection
- **WHEN** the deduplication pass marks one or more candidates as `deduplicated=True`
- **THEN** those candidates SHALL be excluded from the shortlist selection pool
- **THEN** `max_segments_per_asset` SHALL be applied to the remaining non-deduplicated candidates only

#### Scenario: All candidates for an asset are distinct
- **WHEN** no candidates are eliminated by deduplication
- **THEN** shortlist selection SHALL proceed over the full candidate set as before

### Requirement: System SHALL persist prefilter outputs for inspection and reuse
In addition to shortlist status and filtering reason, the generated project state SHALL record deduplication decisions for every candidate segment that was eliminated.

#### Scenario: Segment is eliminated by deduplication
- **WHEN** a candidate is marked deduplicated
- **THEN** its `PrefilterDecision` SHALL record `deduplicated=True`, the `dedup_group_id` of the retained representative, and a human-readable `selection_reason`

#### Scenario: Segment survives deduplication
- **WHEN** a candidate is the retained representative of a duplicate group
- **THEN** its `PrefilterDecision` SHALL have `deduplicated=False` and no `dedup_group_id`
