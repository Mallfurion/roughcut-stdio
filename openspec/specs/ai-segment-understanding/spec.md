# ai-segment-understanding Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL persist structured segment-understanding records
The analyzer SHALL attach structured evidence and understanding records to candidate segments in the generated project state so segment recommendations can be inspected after processing.

#### Scenario: Candidate segment is analyzed
- **WHEN** the analyzer finishes processing a candidate segment
- **THEN** the generated project SHALL contain a persisted evidence bundle for that segment
- **THEN** the generated project SHALL contain a persisted segment-understanding record for that segment

### Requirement: System SHALL support LM Studio with deterministic fallback
The analyzer SHALL support a local LM Studio provider for multimodal segment understanding and SHALL fall back to deterministic structured analysis when the provider is not configured, not reachable, or fails during inference.

#### Scenario: LM Studio is reachable
- **WHEN** `TIMELINE_AI_PROVIDER=lmstudio` is configured and LM Studio responds successfully
- **THEN** analyzed segments SHALL record `lmstudio` as their understanding provider

#### Scenario: LM Studio is unavailable or request handling fails
- **WHEN** LM Studio cannot be used for segment analysis
- **THEN** the analyzer SHALL continue processing with deterministic structured analysis instead of failing the whole run

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
The analyzer SHALL provide runtime controls for fast/full analysis modes, per-asset shortlisting, reduced keyframe counts, downscaled keyframes, bounded concurrency, and on-disk caching.

#### Scenario: Fast mode is enabled
- **WHEN** `TIMELINE_AI_MODE=fast`
- **THEN** only a bounded shortlist of candidate segments per asset SHALL be sent to the expensive provider path
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis

#### Scenario: Cached understanding exists
- **WHEN** a segment has already been analyzed with the same model and prompt version
- **THEN** the analyzer SHALL reuse the cached understanding instead of repeating the provider request

### Requirement: Process SHALL expose AI runtime behavior to the user
The processing step SHALL report configured provider details, effective provider choice, runtime mode, and other local AI runtime settings during a run.

#### Scenario: User starts a process run with AI enabled
- **WHEN** `npm run process` starts with AI configuration present
- **THEN** the process output SHALL disclose provider, model, runtime mode, and cache/concurrency settings

#### Scenario: Segment is skipped by fast-mode shortlisting
- **WHEN** a segment is not sent to LM Studio because of fast-mode shortlisting
- **THEN** its structured understanding SHALL indicate that AI was skipped in fast mode

