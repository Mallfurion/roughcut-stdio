## ADDED Requirements

### Requirement: System SHALL persist richer speech-structure context when available
When transcript-backed analysis derives richer spoken-structure signals beyond basic transcript excerpts or turns, the generated project SHALL preserve enough evidence or review metadata to distinguish those segments from generic speech fallback or simple turn alignment.

#### Scenario: Segment uses richer spoken-structure evidence
- **WHEN** a candidate segment is shaped or scored using richer spoken-structure context
- **THEN** the generated project SHALL preserve enough speech-aware evidence or metadata to make that decision reviewable
- **THEN** downstream inspection SHALL be able to distinguish that case from simple excerpt-backed or turn-aligned speech handling
