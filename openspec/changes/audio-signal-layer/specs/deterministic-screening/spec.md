## MODIFIED Requirements

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments using `audio_energy` and `speech_ratio` as continuous inputs in place of the binary `speech_presence` metric. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used and SHALL behave identically for silent assets.

#### Scenario: Segment in an asset with audio contains measurable speech energy
- **WHEN** a candidate segment has `audio_energy > 0.0` and `speech_ratio > 0.0`
- **THEN** scoring SHALL use those values as continuous inputs to the technical and semantic score paths
- **THEN** the segment SHALL score higher than a silent segment from the same asset, all else equal

#### Scenario: Segment in an asset with audio is silent
- **WHEN** a candidate segment has `audio_energy = 0.0` and `speech_ratio = 0.0` due to silent content within an audio-present asset
- **THEN** scoring SHALL treat that segment equivalently to a segment from a fully silent asset

#### Scenario: Asset has no audio stream
- **WHEN** an asset has no audio stream and all segments receive `audio_energy = 0.0` and `speech_ratio = 0.0`
- **THEN** scoring SHALL produce the same result as the current `speech_presence = 0.0` path
- **THEN** no regression in silent-footage recommendation behavior SHALL occur
