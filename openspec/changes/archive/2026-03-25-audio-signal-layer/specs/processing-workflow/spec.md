## MODIFIED Requirements

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report audio coverage statistics in addition to existing prefilter and VLM reduction statistics. This reporting SHALL be included in `generated/process.log` and in the summary printed at the end of a process run.

#### Scenario: Process run includes assets with audio streams
- **WHEN** `npm run process` completes and at least one asset had an audio stream
- **THEN** the process summary SHALL report the count of assets with audio signal data
- **THEN** the process summary SHALL report the count of segments where `audio_energy > 0.0`
- **THEN** the process summary SHALL report the count of candidate boundary hints contributed by audio energy peaks

#### Scenario: Process run has no assets with audio streams
- **WHEN** `npm run process` completes and all assets are silent or audio extraction failed for all assets
- **THEN** the process summary SHALL indicate that no audio signal data was collected
- **THEN** no error or warning SHALL be emitted for the absence of audio signal
