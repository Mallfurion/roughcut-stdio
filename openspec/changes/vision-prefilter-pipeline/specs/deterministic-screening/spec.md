## MODIFIED Requirements

### Requirement: System SHALL generate candidate segments for each valid asset
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL refine those candidates with a low-cost visual prefilter stage that uses sampled frame or window evidence to identify promising regions. When scene detection is not available or yields no segments, the analyzer SHALL still produce fallback regions, but shortlist construction SHALL prefer feature-driven promising regions over arbitrary fixed windows alone.

#### Scenario: Scene detection is available
- **WHEN** the runtime can use `PySceneDetect`
- **THEN** initial candidate regions SHALL be derived from detected scene boundaries
- **THEN** those regions SHALL be further screened by low-cost visual scoring before downstream shortlist decisions are made

#### Scenario: Scene detection is unavailable
- **WHEN** `PySceneDetect` is unavailable or produces no scenes
- **THEN** the analyzer SHALL generate fallback candidate windows for the asset
- **THEN** the analyzer SHALL still apply low-cost visual screening to determine which fallback regions are most promising

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The analyzer SHALL compute deterministic quality metrics for candidate segments, but those metrics SHALL now operate as a screening and shortlist layer informed by real low-cost visual features rather than only placeholder-first ranking. Deterministic recommendation behavior SHALL remain available even when no VLM provider is used.

#### Scenario: Multiple segments exist for one asset
- **WHEN** an asset has several candidate segments
- **THEN** the analyzer SHALL use prefilter-informed deterministic scoring to build a shortlist before any expensive downstream refinement

#### Scenario: No segment clears the deterministic threshold
- **WHEN** no candidate segment satisfies the current score threshold rules
- **THEN** the analyzer SHALL still keep a fallback segment for that asset so the pipeline can continue deterministically
