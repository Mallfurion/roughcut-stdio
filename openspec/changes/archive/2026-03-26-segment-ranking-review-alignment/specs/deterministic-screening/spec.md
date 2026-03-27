## MODIFIED Requirements

### Requirement: System SHALL produce reviewable deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments using `audio_energy` and `speech_ratio` as continuous inputs in place of the binary `speech_presence` metric. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used and SHALL behave identically for silent assets. For every candidate segment, the analyzer SHALL also persist review-facing recommendation data aligned with the active selection logic, including total and component scores, recommendation outcome, within-asset rank, score gap to the winning segment, and a concise explanation of the strongest score drivers or limiting factors.

#### Scenario: Segment wins recommendation within its asset
- **WHEN** a candidate segment is the highest-ranked selected segment for its asset
- **THEN** its persisted recommendation record SHALL identify it as the winning outcome for that asset
- **THEN** the record SHALL include total score, technical score, semantic score, story score, within-asset rank, and an explanation grounded in the active scoring formula

#### Scenario: Segment does not win recommendation within its asset
- **WHEN** a candidate segment remains a non-winning alternate or backup for its asset
- **THEN** its persisted recommendation record SHALL still include total score, component scores, within-asset rank, and score gap to the winner
- **THEN** the record SHALL explain whether it lost by rank, minimum-score threshold, or alternate-selection gap
