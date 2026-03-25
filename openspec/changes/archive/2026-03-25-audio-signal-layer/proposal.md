## Why

The current prefilter pipeline samples frames and extracts visual signals, but treats audio as a binary property of the asset rather than a continuous signal available at the segment level. `has_speech` is set from stream-presence detection at asset probe time and does not change per segment. This means the pipeline cannot distinguish a loud dialogue beat from a silent cutaway within the same clip, cannot weight speech-rich segments differently from silent stretches, and cannot use audio energy peaks as additional candidate segment boundaries.

Audio analysis is one of the cheapest signals available. ffmpeg already processes every clip during frame extraction. A single `astats` or `silencedetect` pass over the audio track yields per-window RMS energy, peak loudness, and silence ratio without any model inference, new learned weights, or additional runtime cost that scales with dataset size. For a tool whose primary audience includes documentary, vlog, and interview footage, the absence of this signal leaves significant screening leverage on the table.

## What Changes

- Add a per-asset audio signal extraction step that runs once during the prefilter stage alongside frame sampling, using ffmpeg's `astats` filter to collect RMS energy and peak loudness per time window, and `silencedetect` to mark silent regions.
- Introduce an `AudioSignal` record in the prefilter domain that carries per-window `rms_energy`, `peak_loudness`, and `is_silent` for a configurable set of timestamps aligned with the existing frame sampling grid.
- Aggregate per-segment audio metrics into the prefilter metrics snapshot alongside visual signals: `audio_energy`, `speech_ratio`, and `audio_peak`.
- Replace the binary `speech_presence` quality metric currently derived from `has_speech` with a continuous `audio_energy` and `speech_ratio` pair derived from the audio signal extraction.
- Update the scoring system in `scoring.py` to use `audio_energy` and `speech_ratio` as primary inputs in both the technical and semantic score paths, giving well-grounded energy values wherever they exist while retaining the deterministic fallback for assets with no audio stream.
- Use audio energy peaks as additional candidate segment boundary hints, fed into `build_prefilter_segments()` alongside the visual score peaks and scene boundaries that already drive segmentation.
- Extend process reporting to show per-asset audio coverage: how many segments had measurable audio energy, how many were classified as predominantly silent, and whether audio energy contributed to any boundary decisions.
- Keep the deterministic fallback intact: when no audio stream is present or ffmpeg audio extraction fails, `audio_energy` defaults to `0.0` and `speech_ratio` defaults to `0.0`, preserving silent-footage workflow correctness.

## Capabilities

### New Capabilities
- `audio-signal-layer`: per-segment audio energy extraction, silence detection, and audio-aware segmentation hints derived from the existing ffmpeg dependency with no additional model or service requirement.

### Modified Capabilities
- `vision-prefilter-pipeline`: extend the prefilter metrics snapshot and segment scoring inputs to include audio energy and speech ratio alongside the existing visual signals.
- `deterministic-screening`: replace the binary `speech_presence` metric with continuous audio energy values derived from actual audio content rather than stream-presence detection.
- `processing-workflow`: add audio coverage statistics to process-time reporting.

## Impact

- Affected code:
  - `services/analyzer/app/prefilter.py`
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/scoring.py`
  - `services/analyzer/app/domain.py`
- Affected outputs:
  - `generated/project.json` — prefilter metrics snapshot per segment gains `audio_energy`, `speech_ratio`, `audio_peak` fields
  - `generated/process.log` — per-asset audio coverage summary
- Dependencies and systems:
  - `ffmpeg` `astats` and `silencedetect` filters — already required, no new binary dependency
  - existing frame sampling timing grid used to align audio window timestamps
  - deterministic fallback path when audio stream is absent
