## ADDED Requirements

### Requirement: System SHALL support local editor-feedback capture
The product SHALL support capturing explicit editor actions during review and timeline refinement as local feedback records that can be reused by later analyzer behavior.

#### Scenario: Editor rejects or adjusts a recommendation
- **WHEN** the editor rejects a recommended segment, trims it, reorders it, or selects an alternate candidate
- **THEN** the product SHALL record that action as a structured local feedback event
- **THEN** the feedback record SHALL preserve enough context to relate the action back to the original analyzer proposal
