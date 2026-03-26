## MODIFIED Requirements

### Requirement: System SHALL support local transcript-backed analysis during processing
The analyzer SHALL support an optional local transcript backend during process runs and SHALL extract timed transcript spans and transcript excerpts for assets when that backend is enabled and available. The analyzer SHALL also be allowed to use selective transcript targeting and short transcript probes so it does not need to fully transcribe every audio-bearing asset. When transcript evidence is available, the analyzer SHALL be able to derive turn-level transcript structure from that evidence for downstream segmentation and scoring.

#### Scenario: Transcript-backed asset yields turn structure
- **WHEN** transcript spans are available for an asset and the analyzer can derive turn structure from them
- **THEN** the analyzer SHALL preserve turn timing information as a first-class transcript input
- **THEN** downstream segmentation and scoring stages SHALL be able to use that turn structure
