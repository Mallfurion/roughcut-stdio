## ADDED Requirements

### Requirement: Stable Analyzer Service Entry Points During Modularization
The analyzer service SHALL preserve the supported service-level entry points and top-level project data contract while internal responsibilities are moved into dedicated modules.

#### Scenario: Processing entry points remain stable during refactor
- **WHEN** callers use the existing analyzer service entry points for scanning, analysis, project loading, or FCPXML export
- **THEN** they SHALL continue to call the supported `service.py` entry points without needing to import new internal modules directly
- **AND** the returned top-level project, take, timeline, and review payload shapes SHALL remain compatible with the current workflow

### Requirement: Analyzer Pipeline Responsibilities Are Phase-Owned
The analyzer service SHALL assign each major pipeline concern to a dedicated owning module instead of continuing to embed orchestration, transcript policy, segmentation, selection, and review concerns in one file.

#### Scenario: Per-asset analysis is composed from dedicated phases
- **WHEN** the analyzer processes an asset
- **THEN** transcript targeting, candidate creation, boundary refinement, semantic validation, shortlist selection, and downstream enrichment SHALL each be owned by explicit modules or services
- **AND** the pipeline coordinator SHALL compose those phase modules instead of reimplementing their policies inline

### Requirement: AI Runtime Flows Reuse Shared Components
The analyzer service SHALL centralize AI runtime configuration, provider status inspection, evidence preparation, prompt generation, cache helpers, and output normalization behind shared components that provider adapters consume.

#### Scenario: Provider adapters use shared request lifecycle helpers
- **WHEN** an AI provider performs segment understanding or semantic boundary validation
- **THEN** the provider-specific adapter SHALL reuse shared evidence, cache, prompt, and normalization components
- **AND** only provider-specific request execution and provider-specific fallback details SHALL remain inside the adapter implementation

### Requirement: Shared Helpers Have Single Ownership
The analyzer service SHALL define one canonical implementation for each shared policy helper instead of keeping duplicate implementations across analyzer modules.

#### Scenario: Shared policy helpers are reused consistently
- **WHEN** multiple analyzer modules need common concerns such as value clamping, environment parsing, deduplication grouping, or project serialization
- **THEN** they SHALL reuse the canonical shared helper or service for that concern
- **AND** the codebase SHALL not maintain multiple active implementations for the same policy behavior
