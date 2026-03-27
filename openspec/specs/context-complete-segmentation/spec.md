# context-complete-segmentation Specification

## Purpose
TBD - created by archiving the context-complete segment refinement changes. Update Purpose after archive.

## Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis. After deterministic refinement, the analyzer SHALL assemble adjacent refined regions into final narrative units through bounded merge and split operations before recommendation and timeline assembly. For speech-heavy material, transcript-turn structure SHALL be used when available to improve boundary placement, merge decisions, and split decisions. For refined or assembled segments whose boundary confidence is below the configured ambiguity threshold, the analyzer MAY run an optional semantic boundary-validation pass when enabled and within budget, and SHALL preserve deterministic output when that pass does not run. The targeting logic for that pass SHALL be calibrated against evaluation-harness results and MAY include a bounded minimum-target rule when no segment clears the primary threshold.

#### Scenario: Deterministic structure is available for refinement
- **WHEN** a seed region overlaps transcript spans, audio transitions, scene boundaries, or other local boundary cues
- **THEN** the analyzer SHALL use those cues to snap, extend, or trim the seed region
- **THEN** the refined region SHALL become the candidate segment passed downstream

#### Scenario: Deterministic structure is limited
- **WHEN** a seed region lacks transcript, audio, or scene cues
- **THEN** the analyzer SHALL still produce a bounded refined candidate segment using heuristic fallback rules
- **THEN** processing SHALL continue without requiring AI assistance

#### Scenario: Adjacent refined regions form one editorial beat
- **WHEN** two adjacent refined regions from the same asset show continuity evidence such as one transcript turn, a question-answer exchange, or a short continuous action
- **THEN** the analyzer SHALL merge them into one final candidate segment before downstream scoring
- **THEN** the final candidate segment SHALL preserve lineage to both refined regions

#### Scenario: Adjacent refined regions form one spoken turn
- **WHEN** adjacent refined regions from the same asset belong to one transcript turn or one continuous spoken exchange
- **THEN** the analyzer SHALL be allowed to merge them into one final candidate segment
- **THEN** the final candidate SHALL preserve turn-aware lineage for review

#### Scenario: Refined region contains multiple ideas
- **WHEN** a refined region contains multiple transcript turns or another strong internal divider
- **THEN** the analyzer SHALL split that region into separate final candidate segments before downstream scoring
- **THEN** each resulting candidate segment SHALL preserve lineage to the source refined region

#### Scenario: Refined speech region crosses a turn break
- **WHEN** a refined speech-heavy region crosses a strong transcript-turn break
- **THEN** the analyzer SHALL be allowed to split that region at the turn break before downstream scoring
- **THEN** the resulting segments SHALL preserve lineage to the source region

#### Scenario: Adjacent turns form one continuous spoken beat
- **WHEN** adjacent transcript turns from the same asset form one continuous spoken beat such as a monologue continuation or tightly linked question/answer exchange
- **THEN** the analyzer SHALL be allowed to keep or assemble them as one candidate segment
- **THEN** the resulting candidate SHALL preserve speech-aware lineage for review

#### Scenario: Speech-heavy segment ends before the spoken beat completes
- **WHEN** a speech-heavy segment is turn-aligned but still cuts off a larger spoken beat that can be inferred from transcript structure
- **THEN** the analyzer SHALL be allowed to refine or reassemble that segment to preserve the fuller spoken beat
- **THEN** deterministic fallback SHALL remain available if the richer speech structure is weak or unavailable

#### Scenario: Ambiguous segment is semantically validated
- **WHEN** a refined or assembled segment is marked ambiguous, semantic boundary validation is enabled, and runtime budget remains
- **THEN** the analyzer SHALL submit that segment to the configured AI backend for boundary validation
- **THEN** the semantic decision SHALL be persisted alongside the segment provenance

#### Scenario: No segment clears the primary ambiguity threshold
- **WHEN** semantic boundary validation is enabled, runtime budget remains, and no segment crosses the primary ambiguity threshold
- **THEN** the analyzer MAY still select a very small bounded subset of the most ambiguous segments for validation
- **THEN** the generated project SHALL record that minimum-target activation was used

#### Scenario: Ambiguous segment is not semantically validated
- **WHEN** a refined or assembled segment is marked ambiguous but semantic validation is disabled, unavailable, or over budget
- **THEN** the analyzer SHALL keep the deterministic segment unchanged
- **THEN** the generated project SHALL record why semantic validation did not run

### Requirement: System SHALL persist deterministic boundary provenance
Each deterministically refined candidate segment SHALL persist the strategy and confidence used to form its boundaries. When a final candidate segment is produced through merge, split, or semantic validation operations, the analyzer SHALL additionally persist the source lineage, assembly rule family, and semantic-validation status needed for review and downstream inspection.

#### Scenario: Refined segment is written to generated project state
- **WHEN** processing completes successfully
- **THEN** each refined candidate segment SHALL include its boundary strategy, boundary confidence, and source seed provenance

#### Scenario: Assembled segment is written to generated project state
- **WHEN** a final candidate segment was produced by merging or splitting refined regions
- **THEN** the generated project SHALL record the assembled segment's source region lineage and assembly rule family

#### Scenario: Final segment is written to generated project state
- **WHEN** processing completes successfully for a final candidate segment
- **THEN** the generated project SHALL include review-facing provenance for that segment, including boundary strategy, confidence, lineage summary, and semantic-validation status
