## MODIFIED Requirements

### Requirement: Repository SHALL expose an npm-first workflow
The repository workflow SHALL support preparing and validating the configured AI backend through the npm-first commands.

#### Scenario: Setup prepares Moondream local backend
- **WHEN** `npm run setup` is executed with `TIMELINE_AI_PROVIDER=moondream-local`
- **THEN** setup SHALL install the required local runtime dependencies and prepare the configured model cache unless explicitly skipped by configuration

#### Scenario: AI health check validates Moondream local backend
- **WHEN** `npm run check:ai` is executed with `TIMELINE_AI_PROVIDER=moondream-local`
- **THEN** it SHALL verify backend readiness, including model availability and a minimal runtime check
- **THEN** it SHALL exit non-zero when the configured backend is not ready

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report which effective backend is used and whether AI results came from live inference, cache reuse, or fallback.

#### Scenario: Process runs with Moondream local backend
- **WHEN** `process` executes with `TIMELINE_AI_PROVIDER=moondream-local`
- **THEN** process logs and summaries SHALL identify the effective backend, model identity, and direct-runtime result counters
