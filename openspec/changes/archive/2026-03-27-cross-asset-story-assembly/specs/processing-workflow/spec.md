## MODIFIED Requirements

### Requirement: Process SHALL honor configured media roots and write generated artifacts
The process step SHALL read footage from `TIMELINE_MEDIA_DIR` when set and SHALL otherwise fall back to the repository `media/` path. The process step SHALL write generated state under `generated/`, including a project JSON document, processing diagnostics, and the persisted terminal-facing output for the latest run. When project-level story assembly is active, generated state SHALL preserve the sequence rationale used for the final rough timeline.

#### Scenario: Process completes with project-level story assembly
- **WHEN** `npm run process` finishes with story-assembly logic enabled
- **THEN** `generated/project.json` SHALL preserve sequence-level rationale or grouping metadata for the final timeline
