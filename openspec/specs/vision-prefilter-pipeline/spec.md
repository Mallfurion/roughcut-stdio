# vision-prefilter-pipeline Specification

## Purpose
TBD - created by archiving change vision-prefilter-pipeline. Update Purpose after archive.
## Requirements
### Requirement: System SHALL screen footage with low-cost visual signals before VLM analysis
_No change to this requirement. Audio signal extraction runs alongside the visual prefilter stage and does not alter the VLM gating behavior defined here._

### Requirement: System SHALL score sampled visual evidence using cheap, inspectable features
The prefilter stage SHALL score sampled frame and audio window evidence using lightweight features. In addition to the existing visual features (sharpness, blur, motion, stability, distinctiveness, composition proxies), the prefilter SHALL include `audio_energy` and `speech_ratio` in the per-segment metrics snapshot when audio signal data is available.

#### Scenario: Asset has both visual and audio signal data
- **WHEN** the runtime produces both `FrameSignal` and `AudioSignal` records for an asset
- **THEN** the prefilter metrics snapshot SHALL include both visual features and `audio_energy` / `speech_ratio`
- **THEN** both signal types SHALL be aggregated independently and stored in the same per-segment metrics snapshot

#### Scenario: Asset has visual signal data only
- **WHEN** the asset has no audio stream or audio extraction fails
- **THEN** the prefilter metrics snapshot SHALL include visual features as before
- **THEN** `audio_energy` SHALL be `0.0` and `speech_ratio` SHALL be `0.0` in the snapshot

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

