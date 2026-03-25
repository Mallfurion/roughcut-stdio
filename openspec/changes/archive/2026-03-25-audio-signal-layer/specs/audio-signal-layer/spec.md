## ADDED Requirements

### Requirement: Audio signal extraction SHALL be enabled by default and controllable via environment variable
When `TIMELINE_AI_AUDIO_ENABLED` is unset or set to `true`, the analyzer SHALL run the audio signal extraction pass. When set to `false`, all assets SHALL receive fallback `AudioSignal` records (`rms_energy=0.0`, `is_silent=True`, `source="fallback"`) and the pipeline SHALL behave identically to the no-audio-stream path.

#### Scenario: TIMELINE_AI_AUDIO_ENABLED is unset or true
- **WHEN** `TIMELINE_AI_AUDIO_ENABLED` is not set, or is set to `true`
- **THEN** audio signal extraction SHALL proceed as normal for all assets with an audio stream
- **THEN** assets without an audio stream SHALL still receive fallback records

#### Scenario: TIMELINE_AI_AUDIO_ENABLED is false
- **WHEN** `TIMELINE_AI_AUDIO_ENABLED=false`
- **THEN** no ffmpeg audio pass SHALL be run for any asset
- **THEN** all assets SHALL receive fallback `AudioSignal` records regardless of whether they have an audio stream
- **THEN** `audio_energy` and `speech_ratio` SHALL be `0.0` for all segments
- **THEN** no audio boundary hints SHALL be generated

### Requirement: System SHALL extract per-window audio energy from assets with an audio stream
The analyzer SHALL run a per-asset audio extraction pass using ffmpeg to measure RMS energy and peak loudness for windows aligned to the frame sampling timestamps. This pass SHALL produce an `AudioSignal` record per timestamp.

#### Scenario: Asset has an audio stream
- **WHEN** an asset is processed and has an audio stream
- **THEN** the analyzer SHALL extract `rms_energy`, `peak_loudness`, and `is_silent` for each sampled timestamp window
- **THEN** the extraction SHALL use the same timestamp grid as the visual frame sampling step

#### Scenario: Asset has no audio stream
- **WHEN** an asset has no audio stream
- **THEN** the analyzer SHALL produce `AudioSignal` records with `rms_energy=0.0`, `peak_loudness=0.0`, `is_silent=True`, and `source="fallback"` for all timestamps
- **THEN** downstream scoring and segmentation SHALL behave identically to the current silent-footage path

#### Scenario: ffmpeg audio extraction fails
- **WHEN** ffmpeg returns a non-zero exit code during audio extraction for an asset
- **THEN** the analyzer SHALL fall back to the no-audio-stream behavior for that asset without interrupting the pipeline

### Requirement: System SHALL aggregate audio metrics into the prefilter snapshot per segment
The prefilter metrics snapshot for each candidate segment SHALL include `audio_energy` and `speech_ratio` derived from the `AudioSignal` records that overlap the segment's time window.

#### Scenario: Segment window contains audio signal data
- **WHEN** `AudioSignal` records exist within a segment's `[start_sec, end_sec]` range
- **THEN** `audio_energy` SHALL be the mean `rms_energy` of those records, normalized to [0, 1]
- **THEN** `speech_ratio` SHALL be the fraction of those records where `is_silent=False`

#### Scenario: No audio signal data overlaps the segment window
- **WHEN** no `AudioSignal` records fall within the segment's time range
- **THEN** `audio_energy` SHALL default to `0.0` and `speech_ratio` SHALL default to `0.0`

### Requirement: System SHALL use audio energy peaks as additional segment boundary hints
Audio energy peaks SHALL be used as a third source of candidate segment boundary hints alongside scene boundaries and visual score peaks.

#### Scenario: Asset has audio energy peaks above the minimum threshold
- **WHEN** one or more timestamps have `rms_energy` significantly above the asset-level mean
- **THEN** the analyzer SHALL generate a candidate window centered on each peak, using the same window-size formula as visual score peaks
- **THEN** those windows SHALL be merged with scene boundary ranges and visual peak windows and deduplicated before the final candidate list is produced

#### Scenario: Asset has no audio peaks above the threshold
- **WHEN** all audio energy values are at or below the minimum threshold
- **THEN** no audio boundary hints SHALL be generated and segment candidates SHALL be determined by visual and scene signals only

### Requirement: System SHALL replace the binary speech_presence metric with continuous audio metrics
The quality metrics for each candidate segment SHALL use `audio_energy` and `speech_ratio` as inputs in place of the binary `speech_presence` metric.

#### Scenario: Segment in a mixed-audio clip contains speech
- **WHEN** a segment's audio windows are predominantly non-silent and have measurable RMS energy
- **THEN** `audio_energy` and `speech_ratio` SHALL reflect that, producing a higher score contribution than a silent segment from the same asset

#### Scenario: Segment in a mixed-audio clip is silent
- **WHEN** a segment's audio windows are predominantly classified as silent
- **THEN** `audio_energy` and `speech_ratio` SHALL be low, producing a score contribution equivalent to the current `speech_presence=0.0` path
