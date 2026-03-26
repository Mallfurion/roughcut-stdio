## MODIFIED Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis. After deterministic refinement, the analyzer SHALL assemble adjacent refined regions into final narrative units through bounded merge and split operations before recommendation and timeline assembly.

#### Scenario: Adjacent refined regions form one editorial beat
- **WHEN** two adjacent refined regions from the same asset show continuity evidence such as one transcript turn, a question-answer exchange, or a short continuous action
- **THEN** the analyzer SHALL merge them into one final candidate segment before downstream scoring
- **THEN** the final candidate segment SHALL preserve lineage to both refined regions

#### Scenario: Refined region contains multiple ideas
- **WHEN** a refined region contains multiple transcript turns or another strong internal divider
- **THEN** the analyzer SHALL split that region into separate final candidate segments before downstream scoring
- **THEN** each resulting candidate segment SHALL preserve lineage to the source refined region

### Requirement: System SHALL persist deterministic boundary provenance
Each deterministically refined candidate segment SHALL persist the strategy and confidence used to form its boundaries. When a final candidate segment is produced through merge or split operations, the analyzer SHALL additionally persist the assembly lineage and assembly rule family.

#### Scenario: Assembled segment is written to generated project state
- **WHEN** a final candidate segment was produced by merging or splitting refined regions
- **THEN** the generated project SHALL record the assembled segment's source region lineage and assembly rule family
