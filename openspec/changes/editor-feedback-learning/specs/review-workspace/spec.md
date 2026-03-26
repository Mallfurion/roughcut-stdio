## MODIFIED Requirements

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. The desktop review surface SHALL also be able to emit structured local feedback events when the editor accepts, rejects, trims, reorders, or replaces analyzer recommendations.

#### Scenario: Editor changes a recommendation in review
- **WHEN** the editor changes or rejects a recommended segment in the desktop review workflow
- **THEN** the review workspace SHALL emit a structured feedback event for that action
