## MODIFIED Requirements

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. When story-assembly logic changes order or grouping across assets, the desktop review surface SHALL also display concise sequence-level rationale for those decisions.

#### Scenario: Timeline item has story-assembly rationale
- **WHEN** a recommended timeline item includes project-level sequence rationale in generated project state
- **THEN** the desktop UI SHALL display that rationale for editor inspection
