## 1. Domain Model

- [ ] 1.1 Add `AudioSignal` dataclass to `prefilter.py` with fields: `timestamp_sec`, `rms_energy`, `peak_loudness`, `is_silent`, `source`
- [ ] 1.2 Add `audio_energy` and `speech_ratio` fields to the prefilter metrics snapshot produced by `aggregate_segment_prefilter()`
- [ ] 1.3 Remove `speech_presence` from `synthesize_quality_metrics()` in `analysis.py` and replace with `audio_energy` and `speech_ratio` derived from the prefilter snapshot

## 2. Audio Extraction

- [ ] 2.1 Implement `sample_audio_signals(asset, timestamps)` in `prefilter.py` using ffmpeg's `astats` filter to extract per-window RMS energy and peak loudness aligned to the existing frame sampling timestamps
- [ ] 2.2 Implement silence detection using ffmpeg's `silencedetect` filter to mark which windows fall below the silence threshold, producing the `is_silent` flag per `AudioSignal`
- [ ] 2.3 Add a fallback path: when the asset has no audio stream or ffmpeg audio extraction fails, return `AudioSignal` records with `rms_energy=0.0`, `peak_loudness=0.0`, `is_silent=True`, `source="fallback"` for all timestamps

## 3. Prefilter Integration

- [ ] 3.1 Call `sample_audio_signals()` in `analyze_assets()` alongside `sample_asset_signals()`, using the same timestamp grid
- [ ] 3.2 Pass audio signals into `aggregate_segment_prefilter()` and compute `audio_energy` (mean RMS in window) and `speech_ratio` (fraction of non-silent windows) per segment
- [ ] 3.3 Add audio energy peaks to `build_prefilter_segments()` as a third source of boundary hints, using the same peak-window logic as visual score peaks, with a minimum energy threshold to suppress spurious peaks in noisy footage

## 4. Scoring

- [ ] 4.1 Update `scoring.py` to replace `speech_presence` with `audio_energy` and `speech_ratio` as inputs to the technical and semantic score paths
- [ ] 4.2 Verify that silent assets (both `audio_energy=0.0` and `speech_ratio=0.0`) produce the same scoring behavior as the current `speech_presence=0.0` path

## 5. Reporting

- [ ] 5.1 Extend process reporting in `scripts/process.sh` to show per-asset audio coverage: assets with audio signal, assets with no audio stream, and segments where audio energy contributed to boundary generation
- [ ] 5.2 Add `audio_signal_count` and `audio_boundary_hint_count` to the analysis summary stored in `project.analysis_summary`

## 6. Documentation

- [ ] 6.1 Update `docs/analyzer-pipeline.md` to document the audio signal sampling step (Step 2.3 in Phase 2) and its relationship to frame signal sampling and segment boundary generation

## 7. Validation

- [ ] 7.1 Add unit tests for `sample_audio_signals()` covering: successful extraction, no audio stream fallback, and ffmpeg failure fallback
- [ ] 7.2 Add unit tests for `aggregate_segment_prefilter()` verifying that `audio_energy` and `speech_ratio` are computed correctly from `AudioSignal` inputs
- [ ] 7.3 Add a test verifying that a silent asset produces identical scoring output before and after this change
- [ ] 7.4 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [ ] 7.5 Verify `npm run process` produces `generated/project.json` with `audio_energy` and `speech_ratio` fields in at least one candidate segment's prefilter metrics snapshot
- [ ] 7.6 Verify `npm run build:desktop` still succeeds
