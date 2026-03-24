# deterministic-screening Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL ingest source clips, proxies, and source-only footage
The analyzer SHALL discover video files from the configured media roots, classify source clips and proxies, and create assets for valid footage even when no matching proxy exists.

#### Scenario: Matching proxy exists
- **WHEN** a source clip and proxy clip can be matched
- **THEN** the asset SHALL preserve the source path and the matched proxy path

#### Scenario: No proxy exists for a clip
- **WHEN** a valid source clip has no matching proxy
- **THEN** the asset SHALL still be included as source-only media

### Requirement: System SHALL generate candidate segments for each valid asset
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL fall back to deterministic time windows when scene detection is not available or yields no segments.

#### Scenario: Scene detection is available
- **WHEN** the runtime can use `PySceneDetect`
- **THEN** candidate segments SHALL be derived from detected scene boundaries

#### Scenario: Scene detection is unavailable
- **WHEN** `PySceneDetect` is unavailable or produces no scenes
- **THEN** the analyzer SHALL generate fallback candidate windows for the asset

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments, score them, and select zero, one, or multiple recommended segments per asset according to the current deterministic rules.

#### Scenario: Multiple segments exist for one asset
- **WHEN** an asset has several candidate segments
- **THEN** the analyzer SHALL rank them with deterministic scoring before marking recommended segments

#### Scenario: No segment clears the deterministic threshold
- **WHEN** no candidate segment satisfies the current score threshold rules
- **THEN** the analyzer SHALL still keep a fallback segment for that asset

### Requirement: System SHALL assemble a rough timeline from selected segments
The analyzer SHALL build a timeline from recommended segments, preserve source references, and assign simple labels and notes for the resulting rough cut.

#### Scenario: Recommended segments exist across assets
- **WHEN** the analyzer has one or more recommended segments
- **THEN** it SHALL create an ordered timeline with trim ranges and source references

#### Scenario: Silent footage dominates the project
- **WHEN** selected segments are primarily visual and transcript-free
- **THEN** the timeline summary SHALL still describe the cut as a visual progression rather than requiring speech-led structure

