## Context

The current pipeline treats audio as a static property of the asset, not as a signal available for per-segment analysis. `has_speech` is set once during asset probing from stream-presence detection and does not vary across segments. The quality metrics derived from it — `speech_presence` in particular — are binary: a segment from an asset that has any audio stream gets a non-zero `speech_presence` value regardless of whether that specific segment contains speech, silence, or background noise. A segment from an asset with no audio stream gets zero.

This means two things are broken:

First, the scoring system cannot distinguish a spoken beat from a silent cutaway within the same clip. Both segments inherit the same `speech_presence` value, even though one has dialogue that gives it structural utility and the other does not. This weakens scoring accuracy for mixed-audio clips, which are common in documentary and vlog workflows.

Second, audio energy peaks are not used as candidate segment boundaries. The prefilter currently builds segment candidates from scene boundaries and visual score peaks. Loud or speech-rich moments — which are among the strongest editorial candidates in many project types — have no representation in the boundary decision logic at all.

Both problems are solvable with a single ffmpeg pass per asset. The `astats` audio filter produces per-window RMS energy and peak loudness without decoding video frames. The `silencedetect` filter marks silent regions. Neither requires model inference, network access, or new binary dependencies. ffmpeg is already required by the pipeline and already runs on every asset.

Constraints:

- the product stays local-first and silent footage remains a first-class workflow
- the change must not degrade behavior for assets with no audio stream
- the existing `setup -> process -> view -> export` workflow must remain intact
- deterministic fallback must remain available at all times
- Resolve export correctness must not be affected

## Goals / Non-Goals

**Goals:**

- Extract per-segment audio energy and silence metrics from every asset that has an audio stream, using ffmpeg with no new binary or model dependency.
- Replace the binary `speech_presence` quality metric with a continuous `audio_energy` value and a `speech_ratio` value derived from actual audio content.
- Use audio energy peaks as additional candidate segment boundary hints alongside visual score peaks and scene boundaries.
- Persist audio metrics in the prefilter snapshot so segment quality is inspectable and explainable.
- Feed audio metrics into the scoring system so speech-rich and audio-energetic segments are ranked more appropriately relative to silent ones.
- Extend process reporting to show per-asset audio coverage and the number of segments where audio signal contributed.

**Non-Goals:**

- Transcription or speech-to-text. That is handled by the existing transcript provider path.
- Speaker diarization.
- Music versus speech classification.
- Any change to the VLM prompt or model behavior.
- Any change to the FCPXML export or Resolve handoff.
- Any UI change to the desktop review workspace.

## Decisions

### 1. Use ffmpeg's audio filters as the only extraction mechanism

The pipeline already uses ffmpeg for frame extraction. Adding an `astats` pass for audio statistics and a `silencedetect` pass for silence boundaries reuses the same binary with the same operational assumptions (local, no network, no model).

Alternative considered:
- Use `librosa` or `soundfile` for more sophisticated audio analysis (spectral features, pitch, etc.).

Why rejected:
- Unnecessary for the current goal. RMS energy and silence detection are sufficient to replace the binary `speech_presence` and add audio boundary hints. Adding `librosa` would introduce a large dependency with no proportional benefit at this stage.

Alternative considered:
- Derive audio energy from the existing `has_speech` and transcript data.

Why rejected:
- `has_speech` is a stream-presence flag, not a content measurement. Transcripts may not be available in silent or non-speech workflows. Neither gives per-segment energy values.

### 2. Align audio windows to the existing frame sampling grid

The frame sampling step already produces a set of timestamps across the asset at approximately `duration / (target_count + 1)` intervals. Audio energy windows should be centered on the same timestamps so that audio and visual signals can be aggregated together per segment without introducing a separate sampling grid.

Alternative considered:
- Sample audio at a fixed interval independent of the visual sampling grid.

Why rejected:
- Two grids would require reconciliation logic and produce more data without improving accuracy for the segment granularity this pipeline works at (2.5–5.5 second windows).

### 3. Introduce `AudioSignal` as a parallel record to `FrameSignal`

The existing `FrameSignal` dataclass captures per-timestamp visual metrics. An `AudioSignal` dataclass with the same timestamp alignment captures per-window audio metrics: `rms_energy`, `peak_loudness`, and `is_silent`. Both are aggregated per segment in `aggregate_segment_prefilter()`.

Alternative considered:
- Add audio fields directly to `FrameSignal`.

Why rejected:
- `FrameSignal` is extracted from decoded video frames. `AudioSignal` comes from a separate audio decode pass. Merging them would obscure the separation between extraction mechanisms and complicate the fallback logic, since audio extraction can fail independently of frame extraction.

### 4. Replace `speech_presence` with `audio_energy` + `speech_ratio`

`speech_presence` in the quality metrics is currently either `0.92` (asset has speech) or `0.0` (no audio stream). Replace it with:

- `audio_energy` — normalized RMS energy for the segment's time window, 0–1
- `speech_ratio` — fraction of the segment window that is not classified as silent, 0–1

When audio extraction succeeds, both values come from the audio signal. When the asset has no audio stream or audio extraction fails, both default to `0.0`, preserving the existing silent-footage path exactly.

Alternative considered:
- Keep `speech_presence` and add `audio_energy` alongside it.

Why rejected:
- Two overlapping metrics measuring the same thing would make scoring weights harder to reason about and would require careful coordination to avoid double-counting.

### 5. Feed audio energy peaks into segment boundary generation

`build_prefilter_segments()` currently combines scene cut boundaries with visual score peak windows. Audio energy peaks — timestamps where `rms_energy` is significantly above the asset average — should be added as a third source of boundary hints, using the same peak-window logic already used for visual score peaks.

Alternative considered:
- Use audio peaks only for scoring, not for boundary generation.

Why rejected:
- The most valuable editorial moments in speech-heavy footage often correspond to audio energy spikes: a question asked, a reaction, an impact. Restricting audio to scoring means those moments may fall inside a larger window defined by a visual peak nearby, rather than being centred correctly.

### 6. Fallback to `audio_energy=0.0`, `speech_ratio=0.0` when audio is absent

Assets with no audio stream, or any asset where ffmpeg audio extraction returns non-zero exit code, should receive `audio_energy=0.0` and `speech_ratio=0.0` for all their segments. This is semantically accurate (no audio energy) and ensures the scoring and prefilter paths remain identical to the current behavior for silent-footage workflows.

Alternative considered:
- Use a placeholder non-zero value for assets where extraction is uncertain.

Why rejected:
- A non-zero value would incorrectly advantage assets with failed audio extraction over genuinely silent assets.

## Risks / Trade-offs

- [Audio energy does not always correlate with editorial quality] → Mitigation: audio energy is one input among several. It replaces the binary `speech_presence` rather than adding a dominant new signal. Weights should be set conservatively in the first version.
- [ffmpeg audio pass adds processing time per asset] → Mitigation: run the audio pass as a single invocation per asset (not per segment), aligned with frame sampling. The pass is cheap relative to frame extraction and VLM inference.
- [Audio peaks may generate spurious boundary hints in noisy footage] → Mitigation: apply a minimum energy threshold before treating a timestamp as a peak, similar to the minimum score threshold used for visual peaks.
- [Behavior change in scoring may affect users relying on current segment rankings] → Mitigation: the change is a direct improvement over a known-broken metric. The fallback behavior for silent assets is identical.

## Migration Plan

1. Add `AudioSignal` dataclass to `prefilter.py`.
2. Implement `sample_audio_signals()` in `prefilter.py` using ffmpeg `astats` and `silencedetect`.
3. Aggregate audio metrics into `aggregate_segment_prefilter()` alongside existing visual metrics.
4. Feed audio energy peaks into `build_prefilter_segments()` as additional boundary hints.
5. Replace `speech_presence` with `audio_energy` + `speech_ratio` in `synthesize_quality_metrics()` in `analysis.py`.
6. Update `scoring.py` to use `audio_energy` and `speech_ratio` as scoring inputs.
7. Extend process reporting in `process.sh` to show per-asset audio coverage.
8. Update `docs/analyzer-pipeline.md` to document the audio signal step.
9. Add tests for audio signal extraction, aggregation, and fallback behavior.
10. Verify the full pipeline with both audio-present and audio-absent assets.

## Open Questions

- Should audio peak windows use the same window size formula as visual peak windows (`duration / 8`, clamped 2.5–5.5s), or a shorter window to better center on spoken beats?
- What RMS energy threshold distinguishes a meaningful audio peak from background noise? Should this be absolute or relative to the per-asset mean?
- Should the audio pass run as a separate ffmpeg invocation, or can it be combined with the existing frame extraction into a single pass to reduce subprocess overhead?
