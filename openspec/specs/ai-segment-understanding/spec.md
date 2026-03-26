# ai-segment-understanding Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing. When semantic boundary validation runs on an ambiguous segment, the analyzer SHALL also persist the boundary decision, decision reason, validation status, and impact metadata for that segment.

#### Scenario: Candidate segment is analyzed
- **WHEN** the analyzer finishes processing a candidate segment
- **THEN** the generated project SHALL contain a persisted evidence bundle for that segment
- **THEN** the generated project SHALL contain a persisted segment-understanding record for that segment

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
The analyzer SHALL use expensive multimodal analysis only after prefilter shortlist construction, regardless of whether the configured provider is `lmstudio` or `mlx-vlm-local`. Optional semantic boundary validation SHALL remain separately controllable, SHALL run only on eligible ambiguous segments within explicit runtime limits, and SHALL preserve deterministic fallback when it does not run.

#### Scenario: Fast mode with MLX local model
- **WHEN** fast mode is enabled and `mlx-vlm-local` is configured
- **THEN** only the per-asset shortlist SHALL be sent to the embedded model backend
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis

#### Scenario: Boundary validation budget is capped
- **WHEN** semantic boundary validation is enabled with a configured runtime limit
- **THEN** the analyzer SHALL validate only the eligible ambiguous subset that fits within that limit
- **THEN** all remaining segments SHALL keep deterministic output and persisted skip metadata

### Requirement: Process SHALL expose AI runtime behavior to the user
The processing step SHALL report configured provider details, effective provider choice, runtime mode, and other local AI runtime settings during a run.

#### Scenario: User starts a process run with AI enabled
- **WHEN** `npm run process` starts with AI configuration present
- **THEN** the process output SHALL disclose provider, model, runtime mode, and cache/concurrency settings

#### Scenario: Segment is skipped by fast-mode shortlisting
- **WHEN** a segment is not sent to LM Studio because of fast-mode shortlisting
- **THEN** its structured understanding SHALL indicate that AI was skipped in fast mode
