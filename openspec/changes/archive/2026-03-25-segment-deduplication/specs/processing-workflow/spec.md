## MODIFIED Requirements

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report deduplication statistics in addition to existing prefilter and VLM reduction statistics. This reporting SHALL be included in `generated/process.log` and in the summary printed at the end of a process run.

#### Scenario: Process run produces deduplicated candidates
- **WHEN** `npm run process` completes and at least one candidate was eliminated by deduplication
- **THEN** the process summary SHALL report the total number of candidates generated across all assets
- **THEN** the process summary SHALL report the number of candidates eliminated by deduplication
- **THEN** the process summary SHALL report the number of candidates forwarded to shortlist selection after deduplication

#### Scenario: No candidates are deduplicated
- **WHEN** all candidate segments in the run are visually distinct
- **THEN** the process summary SHALL indicate that zero candidates were eliminated by deduplication
- **THEN** no warning or error SHALL be emitted for the absence of deduplication activity
