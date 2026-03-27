## MODIFIED Requirements

### Requirement: System SHALL support project-level story assembly
The analyzer SHALL be able to assemble recommended candidate units into a rough timeline using project-level sequence logic rather than relying only on independent per-asset winners. That sequence logic SHALL be allowed to score continuity, diversity, pacing, repetition control, position-specific fit, and story-prompt fit across the candidate units before final timeline order is chosen. When the editor has applied desktop best-take overrides, story assembly SHALL rebuild from that final override-adjusted selected take set, including assets whose active take was explicitly cleared, rather than the analyzer-selected winners alone.

#### Scenario: Multiple strong units exist across assets
- **WHEN** the analyzer has recommended units from multiple assets for one project
- **THEN** it SHALL be allowed to score continuity, diversity, pacing, repetition control, or role fit across those units before final timeline order is chosen
- **THEN** the resulting timeline SHALL preserve sequence-level rationale for review

#### Scenario: Desktop override changes one asset winner
- **WHEN** the active project state includes a desktop best-take override for an asset
- **THEN** the story-assembly layer SHALL rebuild the final timeline order from the override-adjusted selected takes
- **THEN** the resulting timeline SHALL preserve sequence rationale for the rebuilt order

#### Scenario: Desktop override removes one asset from the selected take set
- **WHEN** the active project state includes an editor-cleared best take for an asset
- **THEN** the story-assembly layer SHALL rebuild the final timeline order without a selected take from that asset
- **THEN** the resulting timeline SHALL preserve sequence rationale for the remaining selected takes
