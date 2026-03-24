## MODIFIED Requirements

### Requirement: Process SHALL report operational status during long runs
The process step SHALL report media discovery, AI provider configuration, fallback decisions, discovered file counts, matched asset counts, progress through the asset list, and the behavior of the prefilter screening stage.

#### Scenario: LM Studio is unavailable
- **WHEN** `TIMELINE_AI_PROVIDER=lmstudio` is configured but LM Studio is unreachable
- **THEN** the process output SHALL state that LM Studio is unavailable
- **THEN** the process output SHALL state that deterministic analysis is being used instead

#### Scenario: Multiple assets are being processed
- **WHEN** a process run analyzes more than one asset
- **THEN** the CLI SHALL show asset progress with elapsed time and estimated remaining time

#### Scenario: Prefilter stage is active
- **WHEN** the process run performs low-cost screening before VLM analysis
- **THEN** the process output SHALL report shortlist or reduction information showing how much footage was filtered before the VLM stage
