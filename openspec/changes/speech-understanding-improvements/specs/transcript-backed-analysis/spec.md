## MODIFIED Requirements

### Requirement: System SHALL support local transcript-backed analysis during processing
The analyzer SHALL support an optional local transcript backend during process runs and SHALL extract timed transcript spans and transcript excerpts for assets when that backend is enabled and available. The analyzer SHALL also be allowed to use selective transcript targeting and short transcript probes so it does not need to fully transcribe every audio-bearing asset. When transcript evidence is available, the analyzer SHALL be able to derive turn-level transcript structure from that evidence for downstream segmentation and scoring, and it SHALL be allowed to derive richer spoken-structure signals such as continuous monologue flow or question/answer continuity from that same evidence.

#### Scenario: Transcript backend is enabled and available
- **WHEN** a process run starts with transcript support enabled and a supported local transcript backend is available
- **THEN** the analyzer SHALL extract timed transcript spans for eligible assets
- **THEN** candidate segments from those assets SHALL include transcript excerpts derived from those spans

#### Scenario: Borderline speech asset is probed before full transcription
- **WHEN** an asset has enough speech evidence to merit transcript inspection but not enough to justify immediate full transcription
- **THEN** the analyzer SHALL be allowed to run a short transcript probe over selected ranges first
- **THEN** the analyzer SHALL promote that asset into the full transcript pass only if the probe detects real transcript text

#### Scenario: Borderline speech asset fails the transcript probe
- **WHEN** the analyzer runs a short transcript probe for an asset and the probe does not detect useful text
- **THEN** the analyzer SHALL skip the full transcript pass for that asset
- **THEN** the run SHALL preserve explicit selective-skip or probe-rejected metadata instead of silently behaving like a silent asset

#### Scenario: Transcript-backed asset yields turn structure
- **WHEN** transcript spans are available for an asset and the analyzer can derive turn structure from them
- **THEN** the analyzer SHALL preserve turn timing information as a first-class transcript input
- **THEN** downstream segmentation and scoring stages SHALL be able to use that turn structure

#### Scenario: Transcript-backed asset yields richer spoken structure
- **WHEN** transcript spans and turns provide enough continuity to identify a larger spoken beat
- **THEN** the analyzer SHALL be allowed to preserve that spoken structure as downstream evidence
- **THEN** downstream segmentation or scoring SHALL be able to distinguish that case from a simple isolated turn

#### Scenario: Transcript backend is disabled
- **WHEN** transcript support is explicitly disabled for a process run
- **THEN** the analyzer SHALL skip transcript extraction
- **THEN** the run SHALL continue without transcript-backed excerpts
