## ADDED Requirements

### Requirement: Speech-aware segmentation SHALL preserve richer spoken beats when evidence exists
When transcript-backed speech structure is available, the analyzer SHALL be allowed to preserve complete spoken beats that span more than a single simple turn, as long as deterministic lineage and fallback behavior remain intact.

#### Scenario: Adjacent turns form one continuous spoken beat
- **WHEN** adjacent transcript turns from the same asset form one continuous spoken beat such as a monologue continuation or tightly linked question/answer exchange
- **THEN** the analyzer SHALL be allowed to keep or assemble them as one candidate segment
- **THEN** the resulting candidate SHALL preserve speech-aware lineage for review

#### Scenario: Speech-heavy segment ends before the spoken beat completes
- **WHEN** a speech-heavy segment is turn-aligned but still cuts off a larger spoken beat that can be inferred from transcript structure
- **THEN** the analyzer SHALL be allowed to refine or reassemble that segment to preserve the fuller spoken beat
- **THEN** deterministic fallback SHALL remain available if the richer speech structure is weak or unavailable
