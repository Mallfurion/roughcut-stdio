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
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL refine those candidates with a low-cost visual prefilter stage that uses sampled frame or window evidence to identify promising regions. The analyzer SHALL first construct seed regions, SHALL deterministically refine those seed regions, SHALL assemble the refined regions into final narrative units when continuity evidence exists, and SHALL use those assembled units as the candidate segments that reach downstream shortlist and recommendation logic.

#### Scenario: Scene detection is available
- **WHEN** the runtime can use `PySceneDetect`
- **THEN** initial seed regions SHALL be derived from detected scene boundaries and other promising low-cost signals
- **THEN** those seed regions SHALL be deterministically refined into candidate segments before downstream shortlist decisions are made

#### Scenario: Scene detection is unavailable
- **WHEN** `PySceneDetect` is unavailable or produces no scenes
- **THEN** the analyzer SHALL generate fallback seed regions for the asset
- **THEN** the analyzer SHALL still refine those fallback seed regions into bounded candidate segments using available local structure

#### Scenario: Continuity evidence exists between adjacent refined regions
- **WHEN** adjacent refined regions from the same asset satisfy the assembly rules for one narrative unit
- **THEN** the analyzer SHALL merge them before candidate scoring and shortlist selection

#### Scenario: No continuity evidence exists
- **WHEN** refined regions do not satisfy merge or split rules
- **THEN** the analyzer SHALL keep the deterministically refined regions as the final candidate segments

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments using `audio_energy` and `speech_ratio` as continuous inputs in place of the binary `speech_presence` metric. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used and SHALL behave identically for silent assets. When transcript-backed excerpts are available, the analyzer SHALL classify and score spoken segments using transcript-backed speech mode. When transcript excerpts are unavailable, the analyzer SHALL still support a speech-aware fallback path for segments with strong speech evidence instead of forcing them into purely visual scoring. When transcript-turn structure is available, the analyzer SHALL be able to incorporate turn completeness and continuity signals into speech-oriented segment scoring.

#### Scenario: Segment in an asset with audio contains measurable speech energy
- **WHEN** a candidate segment has `audio_energy > 0.0` and `speech_ratio > 0.0`
- **THEN** scoring SHALL use those values as continuous inputs to the technical and semantic score paths
- **THEN** the segment SHALL score higher than a silent segment from the same asset, all else equal

#### Scenario: Transcript-backed speech excerpt is present
- **WHEN** an asset has speech and a candidate segment includes a non-empty transcript excerpt
- **THEN** the analyzer SHALL classify that segment as speech for scoring and recommendation behavior
- **THEN** speech-oriented technical, semantic, and story scoring inputs SHALL be applied to that segment

#### Scenario: Transcript excerpt is missing but speech evidence is strong
- **WHEN** an asset has speech, a candidate segment has strong speech evidence, and transcript extraction is unavailable or returns no text for that segment
- **THEN** the analyzer SHALL use a speech-aware fallback path instead of forcing the segment into purely visual scoring
- **THEN** generated review metadata SHALL indicate that speech fallback was used without transcript text

#### Scenario: Spoken segment aligns to a complete turn
- **WHEN** a speech-heavy candidate segment aligns closely to a complete transcript turn or complete spoken exchange
- **THEN** deterministic scoring SHALL be allowed to reward that segment relative to an equally strong but truncated spoken segment

#### Scenario: Segment in an asset with audio is silent
- **WHEN** a candidate segment has `audio_energy = 0.0` and `speech_ratio = 0.0` due to silent content within an audio-present asset
- **THEN** scoring SHALL treat that segment equivalently to a segment from a fully silent asset

#### Scenario: Asset has no audio stream
- **WHEN** an asset has no audio stream and all segments receive `audio_energy = 0.0` and `speech_ratio = 0.0`
- **THEN** scoring SHALL produce the same result as the current `speech_presence = 0.0` path
- **THEN** no regression in silent-footage recommendation behavior SHALL occur

### Requirement: System SHALL assemble a rough timeline from selected segments
The analyzer SHALL build a timeline from recommended segments, preserve source references, and assign simple labels and notes for the resulting rough cut.

#### Scenario: Recommended segments exist across assets
- **WHEN** the analyzer has one or more recommended segments
- **THEN** it SHALL create an ordered timeline with trim ranges and source references

#### Scenario: Silent footage dominates the project
- **WHEN** selected segments are primarily visual and transcript-free
- **THEN** the timeline summary SHALL still describe the cut as a visual progression rather than requiring speech-led structure
