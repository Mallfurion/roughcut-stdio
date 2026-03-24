## ADDED Requirements

### Requirement: System SHALL screen footage with low-cost visual signals before VLM analysis
The analyzer SHALL perform a pre-VLM screening pass over each asset using low-cost visual signals derived from sampled frames or short windows. This screening pass SHALL operate before any multimodal model request is made for that asset.

#### Scenario: Asset enters screening
- **WHEN** an asset is processed
- **THEN** the analyzer SHALL compute prefilter signals before deciding which segments reach the VLM stage

#### Scenario: VLM is disabled or unavailable
- **WHEN** the configured AI provider is deterministic or unavailable
- **THEN** the prefilter stage SHALL still run and produce shortlist-ready screening output

### Requirement: System SHALL score sampled visual evidence using cheap, inspectable features
The prefilter stage SHALL score sampled frame or window evidence using lightweight features such as sharpness, blur, motion, stability, distinctiveness, composition proxies, and optionally additional cheap learned features when available.

#### Scenario: Basic runtime only
- **WHEN** the runtime has only the standard local media toolchain available
- **THEN** the analyzer SHALL still compute a valid screening score using deterministic visual features

#### Scenario: Optional cheap learned scorer is available
- **WHEN** an optional lightweight scorer such as CLIP-style or aesthetic-style scoring is enabled and available
- **THEN** the analyzer MAY incorporate that signal into prefilter scoring without making it a hard dependency

### Requirement: System SHALL build shortlist candidate regions from screening structure
The analyzer SHALL construct shortlist candidate regions from scene boundaries plus visual score structure such as motion changes, score peaks, or deduplicated near-identical runs instead of relying only on fallback fixed windows.

#### Scenario: Strong score region exists inside a longer clip
- **WHEN** a longer asset contains a concentrated visually strong region
- **THEN** the analyzer SHALL be able to produce a shortlist candidate focused on that region instead of only broad fallback windows

#### Scenario: Repetitive or near-identical coverage dominates a clip
- **WHEN** long runs of visually repetitive footage are detected
- **THEN** the analyzer SHALL suppress or collapse those runs during shortlist construction

### Requirement: System SHALL persist prefilter outputs for inspection and reuse
The generated project state SHALL record enough prefilter information to explain which footage was shortlisted and why, including the evidence used to decide whether a segment reached the VLM stage.

#### Scenario: Segment reaches the shortlist
- **WHEN** a candidate region is shortlisted for downstream refinement
- **THEN** the generated project SHALL indicate that the segment was selected by the prefilter stage

#### Scenario: Segment does not reach the shortlist
- **WHEN** a candidate region is screened out before VLM analysis
- **THEN** the generated project SHALL preserve the reason or status indicating that it was filtered before VLM analysis
