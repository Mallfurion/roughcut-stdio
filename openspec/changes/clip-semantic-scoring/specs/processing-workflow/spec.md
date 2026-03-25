## MODIFIED Requirements

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report CLIP scoring statistics and VLM budget utilisation in addition to existing prefilter, deduplication, and AI runtime statistics.

#### Scenario: Process run completes with CLIP enabled
- **WHEN** `npm run process` finishes and `TIMELINE_AI_CLIP_ENABLED=true`
- **THEN** the process summary SHALL report the CLIP model used, the number of segments scored, and the number gated by the CLIP threshold
- **THEN** the process summary SHALL report whether the global VLM budget cap was binding and the final VLM target count as a percentage of all candidates

#### Scenario: Process run completes with CLIP disabled
- **WHEN** `npm run process` finishes and CLIP was not active
- **THEN** the process summary SHALL report the global VLM budget utilisation without CLIP statistics
- **THEN** no CLIP-related fields SHALL appear in `generated/process.log`
