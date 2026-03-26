## MODIFIED Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis. After deterministic refinement, the analyzer SHALL assemble adjacent refined regions into final narrative units through bounded merge and split operations before recommendation and timeline assembly. For speech-heavy material, transcript-turn structure SHALL be used when available to improve boundary placement, merge decisions, and split decisions.

#### Scenario: Adjacent refined regions form one spoken turn
- **WHEN** adjacent refined regions from the same asset belong to one transcript turn or one continuous spoken exchange
- **THEN** the analyzer SHALL be allowed to merge them into one final candidate segment
- **THEN** the final candidate SHALL preserve turn-aware lineage for review

#### Scenario: Refined speech region crosses a turn break
- **WHEN** a refined speech-heavy region crosses a strong transcript-turn break
- **THEN** the analyzer SHALL be allowed to split that region at the turn break before downstream scoring
- **THEN** the resulting segments SHALL preserve lineage to the source region
