## MODIFIED Requirements

### Requirement: System SHALL support LM Studio with deterministic fallback
The analyzer SHALL support at least three AI backends for segment understanding:

- `deterministic`
- `lmstudio`
- `moondream-local`

The analyzer SHALL keep deterministic fallback available whenever the configured backend cannot be used successfully.

#### Scenario: Moondream local backend is configured and ready
- **WHEN** `TIMELINE_AI_PROVIDER=moondream-local` is configured and the local model runtime is ready
- **THEN** shortlisted segment images SHALL be analyzed directly by the embedded Moondream backend
- **THEN** those analyzed segments SHALL record `moondream-local` as their understanding provider

#### Scenario: Moondream local backend is configured but not ready
- **WHEN** `TIMELINE_AI_PROVIDER=moondream-local` is configured but the local model cannot be loaded or used
- **THEN** `process` SHALL continue with deterministic fallback analysis instead of failing the whole run
- **THEN** runtime reporting SHALL make the fallback explicit

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
The analyzer SHALL use expensive multimodal analysis only after prefilter shortlist construction, regardless of whether the configured provider is `lmstudio` or `moondream-local`.

#### Scenario: Fast mode with direct local model
- **WHEN** fast mode is enabled and `moondream-local` is configured
- **THEN** only the per-asset shortlist SHALL be sent to the embedded model backend
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis
