## MODIFIED Requirements

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments using `audio_energy` and `speech_ratio` as continuous inputs in place of the binary `speech_presence` metric. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used and SHALL behave identically for silent assets. When transcript-backed excerpts are available, the analyzer SHALL classify and score spoken segments using transcript-backed speech mode. When transcript excerpts are unavailable, the analyzer SHALL still support a speech-aware fallback path for segments with strong speech evidence instead of forcing them into purely visual scoring.

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

#### Scenario: Segment in an asset with audio is silent
- **WHEN** a candidate segment has `audio_energy = 0.0` and `speech_ratio = 0.0` due to silent content within an audio-present asset
- **THEN** scoring SHALL treat that segment equivalently to a segment from a fully silent asset

#### Scenario: Asset has no audio stream
- **WHEN** an asset has no audio stream and all segments receive `audio_energy = 0.0` and `speech_ratio = 0.0`
- **THEN** scoring SHALL produce the same result as the current `speech_presence = 0.0` path
- **THEN** no regression in silent-footage recommendation behavior SHALL occur

