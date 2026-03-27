# ai-segment-understanding Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing. When semantic boundary validation runs on an ambiguous segment, the analyzer SHALL also persist the boundary decision, decision reason, validation status, and impact metadata for that segment. The persisted segment state SHALL also remain reviewable enough to distinguish whether a segment was shortlisted, keyframed, CLIP scored or gated, deduplicated, VLM analyzed, budget-capped, or carried forward by deterministic fallback.

#### Scenario: Candidate segment is analyzed with model-backed evidence
- **WHEN** the analyzer finishes model-backed processing for a shortlisted candidate segment
- **THEN** the generated project SHALL contain a persisted evidence bundle for that segment
- **THEN** the generated project SHALL contain a persisted segment-understanding record for that segment
- **THEN** the generated project SHALL make its analysis path reviewable as a model-analyzed segment

#### Scenario: Candidate segment is skipped before model analysis
- **WHEN** a candidate segment is not sent to a model because of shortlisting, deduplication, CLIP gating, or budget capping
- **THEN** the generated project SHALL still make that segment's analysis path reviewable
- **THEN** the persisted state SHALL distinguish deterministic fallback from model-backed analysis

#### Scenario: Semantic boundary validation runs
- **WHEN** the analyzer performs semantic boundary validation on an ambiguous segment
- **THEN** the generated project SHALL persist the validation result and validation status for that segment

#### Scenario: Semantic boundary validation changes a segment
- **WHEN** semantic boundary validation trims, extends, or splits a segment
- **THEN** the generated project SHALL persist the validation impact alongside the segment provenance
- **THEN** downstream review SHALL be able to distinguish a no-op validation from a materially changed boundary

### Requirement: System SHALL include transcript context in segment evidence when available
The analyzer SHALL include transcript excerpts in persisted segment evidence and AI understanding prompts when transcript-backed analysis is available. When transcript-backed analysis is unavailable, the analyzer SHALL persist explicit fallback context rather than silently omitting the distinction.

#### Scenario: Transcript excerpt exists for a segment
- **WHEN** a candidate segment has a non-empty transcript excerpt
- **THEN** the persisted evidence bundle SHALL include that excerpt
- **THEN** AI understanding prompts and persisted understanding context SHALL use that transcript excerpt

#### Scenario: Speech-aware fallback is used without transcript text
- **WHEN** a segment is treated as speech-relevant through fallback behavior and transcript text is unavailable
- **THEN** the persisted evidence or review metadata SHALL indicate that speech fallback was used without transcript-backed text
- **THEN** downstream inspection SHALL be able to distinguish this case from a truly silent visual segment

#### Scenario: Transcript extraction is selectively skipped for an asset
- **WHEN** transcript support is enabled but the analyzer skips or rejects transcript extraction for an asset through selective targeting or probing
- **THEN** persisted segment review metadata SHALL indicate that transcript extraction was selectively skipped
- **THEN** downstream inspection SHALL be able to distinguish that case from provider-disabled, provider-unavailable, and excerpt-available states

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
The analyzer SHALL use expensive multimodal analysis only after prefilter shortlist construction, regardless of whether the configured provider is `lmstudio` or `mlx-vlm-local`. Optional semantic boundary validation SHALL remain separately controllable, SHALL consume an explicit run-scoped runtime budget, and SHALL preserve deterministic fallback when it does not run. Eligible ambiguous segments that do not fit within the remaining run budget SHALL preserve explicit persisted skip metadata rather than behaving as if the budget refreshed per asset.

#### Scenario: Fast mode with MLX local model
- **WHEN** fast mode is enabled and `mlx-vlm-local` is configured
- **THEN** only the per-asset shortlist SHALL be sent to the embedded model backend
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis

#### Scenario: Boundary validation budget is capped
- **WHEN** semantic boundary validation is enabled with a configured runtime limit
- **THEN** the analyzer SHALL validate only the eligible ambiguous subset that fits within the remaining run-scoped budget
- **THEN** all remaining eligible segments SHALL keep deterministic output and persisted over-budget skip metadata

### Requirement: Process SHALL expose AI runtime behavior to the user
The processing step SHALL report configured provider details, effective provider choice, runtime mode, and other local AI runtime settings during a run. When the active provider cannot honor the configured concurrency directly, the process diagnostics SHALL preserve the effective execution context used for that run so the operator can distinguish configured settings from actual runtime behavior.

#### Scenario: User starts a process run with AI enabled
- **WHEN** `npm run process` starts with AI configuration present
- **THEN** the process output SHALL disclose provider, model, runtime mode, and cache/concurrency settings

#### Scenario: Provider execution differs from configured concurrency
- **WHEN** the active AI provider serializes or otherwise reduces model execution below the configured concurrency
- **THEN** generated process diagnostics SHALL preserve that effective execution context
- **THEN** downstream benchmark review SHALL be able to distinguish configured concurrency from effective AI execution

### Requirement: System SHALL persist richer speech-structure context when available
When transcript-backed analysis derives richer spoken-structure signals beyond basic transcript excerpts or turns, the generated project SHALL preserve enough evidence or review metadata to distinguish those segments from generic speech fallback or simple turn alignment.

#### Scenario: Segment uses richer spoken-structure evidence
- **WHEN** a candidate segment is shaped or scored using richer spoken-structure context
- **THEN** the generated project SHALL preserve enough speech-aware evidence or metadata to make that decision reviewable
- **THEN** downstream inspection SHALL be able to distinguish that case from simple excerpt-backed or turn-aligned speech handling

### Requirement: System SHALL make AI-path activation and fallback explicit
The analyzer SHALL preserve explicit state for whether expensive AI-related paths activated, were skipped, were gated, or degraded to fallback behavior during a run.

#### Scenario: Optional AI path is gated or skipped
- **WHEN** an optional AI-related path does not run because of shortlisting, readiness, or runtime gating
- **THEN** generated project state or process diagnostics SHALL preserve that reason
- **THEN** downstream inspection SHALL be able to distinguish intentional gating from failure

#### Scenario: Optional AI path degrades to fallback
- **WHEN** a configured AI-related path cannot complete and the analyzer falls back to deterministic behavior
- **THEN** generated state or diagnostics SHALL preserve the degraded-to-fallback status
- **THEN** the run SHALL remain inspectable enough to explain that change in behavior

