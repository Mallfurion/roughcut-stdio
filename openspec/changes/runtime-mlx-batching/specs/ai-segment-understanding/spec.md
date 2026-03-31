## MODIFIED Requirements

### Requirement: System SHALL support LM Studio with deterministic fallback
The analyzer SHALL support the following AI backends for segment understanding:

- `deterministic`
- `lmstudio`
- `mlx-vlm-local`

The embedded local backend SHALL no longer be `moondream-local`. Deterministic fallback SHALL remain available whenever the configured backend cannot be used successfully. When `mlx-vlm-local` can analyze multiple shortlisted segments from the same asset in one local-model invocation, the analyzer SHALL be allowed to satisfy those segment-understanding requests through a batched local execution path instead of one model call per segment.

#### Scenario: MLX local backend is configured and ready
- **WHEN** `TIMELINE_AI_PROVIDER=mlx-vlm-local` is configured and the local MLX runtime is ready
- **THEN** shortlisted segment images SHALL be analyzed directly by the embedded MLX backend
- **THEN** those analyzed segments SHALL record `mlx-vlm-local` as their understanding provider

#### Scenario: MLX local backend batches shortlisted segments for one asset
- **WHEN** `mlx-vlm-local` receives multiple non-cached shortlisted segments from the same asset and the local runtime supports batch execution
- **THEN** the analyzer SHALL be allowed to submit those pending segment-understanding requests through one batched local-model invocation
- **THEN** the generated project SHALL still persist one evidence bundle and one understanding record per segment

#### Scenario: MLX local backend returns an incomplete batch result
- **WHEN** a batched `mlx-vlm-local` response omits, corrupts, or otherwise fails to produce a usable result for one or more requested segments
- **THEN** the analyzer SHALL preserve valid batch results for the other segments
- **THEN** only the missing or invalid segment results SHALL fall back to deterministic understanding

#### Scenario: MLX local backend is configured but not ready
- **WHEN** `TIMELINE_AI_PROVIDER=mlx-vlm-local` is configured but the local model runtime cannot be loaded or used
- **THEN** `process` SHALL continue with deterministic fallback analysis instead of failing the whole run
- **THEN** runtime reporting SHALL make the fallback explicit

### Requirement: Process SHALL expose AI runtime behavior to the user
The processing step SHALL report configured provider details, effective provider choice, runtime mode, and other local AI runtime settings during a run. When the active provider cannot honor the configured concurrency directly, the process diagnostics SHALL preserve the effective execution context used for that run so the operator can distinguish configured settings from actual runtime behavior. When the active provider executes model-backed segment understanding in batches, the diagnostics SHALL preserve that batched-local execution context instead of presenting the run as plain serialized single-segment work.

#### Scenario: User starts a process run with AI enabled
- **WHEN** `npm run process` starts with AI configuration present
- **THEN** the process output SHALL disclose provider, model, runtime mode, and cache/concurrency settings

#### Scenario: Provider execution differs from configured concurrency
- **WHEN** the active AI provider serializes or otherwise reduces model execution below the configured concurrency
- **THEN** generated process diagnostics SHALL preserve that effective execution context
- **THEN** downstream benchmark review SHALL be able to distinguish configured concurrency from effective AI execution

#### Scenario: MLX local execution is batched
- **WHEN** `mlx-vlm-local` satisfies multiple segment-understanding requests through batched local execution
- **THEN** generated process diagnostics SHALL preserve that the run used batched local-model execution rather than serialized single-segment execution
- **THEN** downstream benchmark review SHALL remain able to distinguish live segment volume from live provider-call volume
