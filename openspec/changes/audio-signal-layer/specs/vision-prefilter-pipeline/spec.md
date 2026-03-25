## MODIFIED Requirements

### Requirement: System SHALL screen footage with low-cost visual signals before VLM analysis
_No change to this requirement. Audio signal extraction runs alongside the visual prefilter stage and does not alter the VLM gating behavior defined here._

### Requirement: System SHALL score sampled visual evidence using cheap, inspectable features
The prefilter stage SHALL score sampled frame and audio window evidence using lightweight features. In addition to the existing visual features (sharpness, blur, motion, stability, distinctiveness, composition proxies), the prefilter SHALL include `audio_energy` and `speech_ratio` in the per-segment metrics snapshot when audio signal data is available.

#### Scenario: Asset has both visual and audio signal data
- **WHEN** the runtime produces both `FrameSignal` and `AudioSignal` records for an asset
- **THEN** the prefilter metrics snapshot SHALL include both visual features and `audio_energy` / `speech_ratio`
- **THEN** both signal types SHALL be aggregated independently and stored in the same per-segment metrics snapshot

#### Scenario: Asset has visual signal data only
- **WHEN** the asset has no audio stream or audio extraction fails
- **THEN** the prefilter metrics snapshot SHALL include visual features as before
- **THEN** `audio_energy` SHALL be `0.0` and `speech_ratio` SHALL be `0.0` in the snapshot

### Requirement: System SHALL build shortlist candidate regions from screening structure
The analyzer SHALL construct shortlist candidate regions from scene boundaries plus visual score structure AND audio energy peaks. Audio energy peaks above a minimum threshold SHALL be treated as boundary hints alongside motion peaks and score peaks.

#### Scenario: Audio energy peak exists outside a visual score peak window
- **WHEN** a timestamp has high `rms_energy` and does not overlap an existing visual peak window
- **THEN** the analyzer SHALL generate a candidate window centered on that audio peak
- **THEN** that window SHALL be merged and deduplicated with other candidate ranges before shortlist selection

#### Scenario: Audio energy peak overlaps an existing visual peak window
- **WHEN** a timestamp has high `rms_energy` and falls within an existing candidate window at 90% or greater overlap
- **THEN** no additional window SHALL be generated for that audio peak
