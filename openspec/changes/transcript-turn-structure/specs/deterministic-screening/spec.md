## MODIFIED Requirements

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments using `audio_energy` and `speech_ratio` as continuous inputs in place of the binary `speech_presence` metric. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used and SHALL behave identically for silent assets. When transcript-turn structure is available, the analyzer SHALL be able to incorporate turn completeness and continuity signals into speech-oriented segment scoring.

#### Scenario: Spoken segment aligns to a complete turn
- **WHEN** a speech-heavy candidate segment aligns closely to a complete transcript turn or complete spoken exchange
- **THEN** deterministic scoring SHALL be allowed to reward that segment relative to an equally strong but truncated spoken segment
