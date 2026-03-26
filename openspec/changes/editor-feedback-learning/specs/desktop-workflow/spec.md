## MODIFIED Requirements

### Requirement: Desktop app SHALL provide a guided local workflow
The product SHALL provide a Tauri-based desktop workflow for the local Mac usage model instead of relying on terminal-first and browser-first interaction as the primary user experience. When review actions are taken, the workflow SHALL be able to preserve them as local feedback records without blocking processing, review, or export.

#### Scenario: Editor finishes a review session with adjustments
- **WHEN** the editor makes recommendation or timeline adjustments during a review session
- **THEN** the desktop app SHALL preserve those actions as local feedback records
- **THEN** the user SHALL still be able to export or continue editing without a separate save-only step
