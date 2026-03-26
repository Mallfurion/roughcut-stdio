## ADDED Requirements

### Requirement: System SHALL support project-level story assembly
The analyzer SHALL be able to assemble recommended candidate units into a rough timeline using project-level sequence logic rather than relying only on independent per-asset winners.

#### Scenario: Multiple strong units exist across assets
- **WHEN** the analyzer has recommended units from multiple assets for one project
- **THEN** it SHALL be allowed to score continuity, diversity, pacing, or role fit across those units before final timeline order is chosen
- **THEN** the resulting timeline SHALL preserve sequence-level rationale for review
