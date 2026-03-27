# story-assembly Specification

## Purpose
TBD - created by archiving change cross-asset-story-assembly. Update Purpose after archive.
## Requirements
### Requirement: System SHALL support project-level story assembly
The analyzer SHALL be able to assemble recommended candidate units into a rough timeline using project-level sequence logic rather than relying only on independent per-asset winners. That sequence logic SHALL be allowed to score continuity, diversity, pacing, repetition control, position-specific fit, and story-prompt fit across the candidate units before final timeline order is chosen.

#### Scenario: Multiple strong units exist across assets
- **WHEN** the analyzer has recommended units from multiple assets for one project
- **THEN** it SHALL be allowed to score continuity, diversity, pacing, repetition control, or role fit across those units before final timeline order is chosen
- **THEN** the resulting timeline SHALL preserve sequence-level rationale for review

### Requirement: Story assembly SHALL consider position-specific sequence fit
The story-assembly layer SHALL be allowed to evaluate opener, middle, and release suitability when selecting and ordering the final rough-cut sequence.

#### Scenario: Multiple plausible openers exist
- **WHEN** several recommended units could plausibly start the rough cut
- **THEN** the analyzer SHALL be allowed to prefer the opener with stronger project-level fit rather than relying only on local segment score
- **THEN** the final timeline SHALL record enough rationale to explain that choice

#### Scenario: Adjacent units are too repetitive
- **WHEN** adjacent candidate units would create a repetitive sequence in mode, role, or beat type
- **THEN** the analyzer SHALL be allowed to prefer a less repetitive sequence even if the replaced local unit had a slightly stronger standalone score
- **THEN** the resulting timeline SHALL preserve the sequence rationale for that tradeoff
