## MODIFIED Requirements

### Requirement: System SHALL support LM Studio with deterministic fallback
The analyzer SHALL support a local LM Studio provider for multimodal segment understanding, but LM Studio SHALL be used only after the low-cost prefilter stage has shortlisted promising candidate regions. The analyzer SHALL fall back to deterministic structured analysis when the provider is not configured, not reachable, or fails during inference.

#### Scenario: LM Studio is reachable
- **WHEN** `TIMELINE_AI_PROVIDER=lmstudio` is configured and LM Studio responds successfully
- **THEN** only prefilter-shortlisted segments SHALL be sent through the LM Studio analysis path
- **THEN** analyzed shortlisted segments SHALL record `lmstudio` as their understanding provider

#### Scenario: LM Studio is unavailable or request handling fails
- **WHEN** LM Studio cannot be used for segment analysis
- **THEN** the analyzer SHALL continue processing with deterministic structured analysis instead of failing the whole run
- **THEN** the prefilter shortlist SHALL still be available for deterministic downstream behavior

### Requirement: System SHALL provide practical local-runtime controls for AI analysis
The analyzer SHALL provide runtime controls for fast/full analysis modes, per-asset shortlisting, reduced keyframe counts, downscaled keyframes, bounded concurrency, and on-disk caching. These controls SHALL operate after prefilter shortlist construction so local multimodal analysis runs only on candidate regions that have already passed cheap visual screening.

#### Scenario: Fast mode is enabled
- **WHEN** `TIMELINE_AI_MODE=fast`
- **THEN** only a bounded shortlist of prefilter-selected candidate segments per asset SHALL be sent to the expensive provider path
- **THEN** non-shortlisted segments SHALL still receive deterministic structured analysis

#### Scenario: Cached understanding exists
- **WHEN** a segment has already been analyzed with the same model and prompt version
- **THEN** the analyzer SHALL reuse the cached understanding instead of repeating the provider request
