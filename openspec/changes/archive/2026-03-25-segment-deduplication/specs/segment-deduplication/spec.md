## ADDED Requirements

### Requirement: System SHALL detect and suppress near-duplicate candidate segments within each asset
After prefilter scoring and before shortlist selection, the analyzer SHALL compare candidate segments from the same asset for visual similarity and eliminate all but the highest-scoring representative from each group of near-duplicates.

#### Scenario: Two candidates cover visually identical content
- **WHEN** two candidate segments from the same asset have a histogram intersection score at or above `TIMELINE_DEDUP_THRESHOLD`
- **THEN** the segment with the lower prefilter score SHALL be marked `deduplicated=True`
- **THEN** the segment with the lower prefilter score SHALL receive a `dedup_group_id` matching the retained segment's ID
- **THEN** only the retained segment SHALL be eligible for shortlist selection and VLM targeting

#### Scenario: Two candidates cover visually distinct content
- **WHEN** two candidate segments from the same asset have a histogram intersection score below `TIMELINE_DEDUP_THRESHOLD`
- **THEN** both candidates SHALL remain eligible for shortlist selection independently

#### Scenario: Asset has only one candidate segment
- **WHEN** an asset produces fewer than two candidate segments
- **THEN** the deduplication pass SHALL be skipped for that asset and the single candidate SHALL proceed unchanged

### Requirement: System SHALL compute visual similarity from already-extracted frame signals
The deduplication pass SHALL derive segment histograms from the grayscale `FrameSignal` records already collected during the prefilter frame sampling step. No additional frame extraction SHALL be required.

#### Scenario: FrameSignal records overlap the segment window
- **WHEN** one or more `FrameSignal` records fall within a segment's `[start_sec, end_sec]` range
- **THEN** the segment histogram SHALL be computed from those records' pixel data bucketed into 16 luminance bins

#### Scenario: No FrameSignal records overlap the segment window
- **WHEN** no `FrameSignal` records fall within a segment's time range
- **THEN** the segment SHALL receive a uniform histogram and SHALL not be eliminated by deduplication

### Requirement: System SHALL preserve deduplicated candidates in generated project state
Eliminated candidates SHALL remain in `generated/project.json` with their full prefilter record. Nothing SHALL be silently discarded.

#### Scenario: Segment is eliminated by deduplication
- **WHEN** a candidate segment is marked `deduplicated=True`
- **THEN** it SHALL appear in `generated/project.json` with `prefilter.deduplicated=True`, a valid `prefilter.dedup_group_id`, and an updated `prefilter.selection_reason` naming the retained candidate
- **THEN** it SHALL NOT appear in the prefilter shortlist
- **THEN** it SHALL NOT receive keyframe extraction or VLM targeting

### Requirement: System SHALL support a configurable similarity threshold
The deduplication similarity threshold SHALL be adjustable without code changes.

#### Scenario: Custom threshold is set
- **WHEN** `TIMELINE_DEDUP_THRESHOLD` is set to a value between 0.0 and 1.0
- **THEN** the deduplication pass SHALL use that value as the minimum histogram intersection score for grouping candidates as near-duplicates

#### Scenario: No threshold is configured
- **WHEN** `TIMELINE_DEDUP_THRESHOLD` is not set
- **THEN** the deduplication pass SHALL use a default threshold of `0.85`

### Requirement: System SHALL support CLIP-based similarity as an optional upgrade
When `TIMELINE_AI_CLIP_ENABLED=true` is set and `open-clip-torch` is installed, the deduplication pass MAY use CLIP embedding cosine similarity instead of histogram intersection.

#### Scenario: CLIP is enabled and available
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is importable
- **THEN** the deduplication pass SHALL use CLIP keyframe embedding cosine similarity as the comparison metric
- **THEN** the threshold semantics and all other deduplication behavior SHALL remain unchanged

#### Scenario: CLIP is enabled but not installed
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` but `open-clip-torch` is not importable
- **THEN** the deduplication pass SHALL fall back to histogram intersection silently
- **THEN** no error SHALL be raised for the missing package during deduplication
