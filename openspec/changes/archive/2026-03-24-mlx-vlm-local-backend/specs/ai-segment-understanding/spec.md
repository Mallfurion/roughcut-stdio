## MODIFIED Requirements

### Requirement: System SHALL support LM Studio with deterministic fallback
The analyzer SHALL support the following AI backends for segment understanding:

- `deterministic`
- `lmstudio`
- `mlx-vlm-local`

The embedded local backend SHALL no longer be `moondream-local`. Deterministic fallback SHALL remain available whenever the configured backend cannot be used successfully.

#### Scenario: MLX local backend is configured and ready
- **WHEN** `TIMELINE_AI_PROVIDER=mlx-vlm-local` is configured and the local MLX runtime is ready
- **THEN** shortlisted segment images SHALL be analyzed directly by the embedded MLX backend
- **THEN** those analyzed segments SHALL record `mlx-vlm-local` as their understanding provider

#### Scenario: MLX local backend is configured but not ready
- **WHEN** `TIMELINE_AI_PROVIDER=mlx-vlm-local` is configured but the local model runtime cannot be loaded or used
- **THEN** `process` SHALL continue with deterministic fallback analysis instead of failing the whole run
- **THEN** runtime reporting SHALL make the fallback explicit

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
The analyzer SHALL use expensive multimodal analysis only after prefilter shortlist construction, regardless of whether the configured provider is `lmstudio` or `mlx-vlm-local`.

#### Scenario: Fast mode with MLX local model
- **WHEN** fast mode is enabled and `mlx-vlm-local` is configured
- **THEN** only the per-asset shortlist SHALL be sent to the embedded model backend
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis
