## MODIFIED Requirements

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
