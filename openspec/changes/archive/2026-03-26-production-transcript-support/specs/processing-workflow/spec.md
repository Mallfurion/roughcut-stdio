## ADDED Requirements

### Requirement: Process SHALL report transcript runtime status
The process workflow SHALL report transcript runtime configuration and transcript availability alongside existing AI/runtime diagnostics in generated process artifacts and terminal-facing output. This reporting SHALL include whether assets were targeted for full transcription, skipped, loaded from transcript cache, probed, or rejected after probing.

#### Scenario: Transcript support is enabled and available
- **WHEN** `npm run process` starts with transcript support enabled and a supported backend available
- **THEN** process output SHALL disclose that transcript extraction is active
- **THEN** generated process artifacts SHALL record transcript runtime status for the run

#### Scenario: Selective transcript probing is active
- **WHEN** the analyzer uses transcript targeting or short transcript probes during a process run
- **THEN** generated process artifacts SHALL record counts for targeted, skipped, probed, probe-rejected, transcribed, and cached transcript assets
- **THEN** terminal-facing process output SHALL include the same counters in the run summary

#### Scenario: Transcript support is enabled but unavailable
- **WHEN** `npm run process` starts with transcript support enabled but the configured backend cannot be used
- **THEN** process output SHALL disclose that transcript extraction is unavailable and that fallback behavior will be used
- **THEN** generated process artifacts SHALL preserve that transcript-unavailable status after the run
