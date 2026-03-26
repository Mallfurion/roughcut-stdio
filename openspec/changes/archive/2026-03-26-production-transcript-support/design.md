## Context

The analyzer already has transcript-oriented code paths, including `TranscriptSpan`, `FasterWhisperAdapter`, transcript-aware boundary refinement, and transcript excerpts in segment evidence. Those paths are currently exercised only in tests or explicit dependency injection. The production process entrypoint does not supply a transcript provider, so `analyze_assets()` falls back to `NoOpTranscriptProvider`. As a result, clips with clear speech activity still carry empty `transcript_excerpt` values in `generated/project.json`, and downstream scoring reclassifies them as visual instead of speech.

This change needs to fix two linked failures:

1. Production runs need a real transcript provider when local transcript tooling is installed.
2. Speech-heavy clips need a deterministic fallback path when transcript extraction is unavailable, incomplete, or disabled.

After implementation, a third requirement is now explicit:

3. Local transcript support must not force a full transcription pass on every audio-bearing asset when a cheaper probe can reject weak candidates first.

The solution must remain local-first, keep silent-footage workflows valid, and avoid turning transcript extraction into a hard prerequisite for processing.

## Goals / Non-Goals

**Goals:**
- Wire transcript extraction into the production analyzer path for local process runs.
- Add explicit transcript runtime controls and runtime-status reporting.
- Preserve transcript spans and transcript excerpts as first-class analyzer evidence when available.
- Improve speech-mode classification and ranking when transcript support is unavailable by using strong speech evidence as a fallback signal.
- Reduce local transcript overhead by using selective transcript targeting and cheap probe passes on borderline assets.
- Keep processing resilient when transcript dependencies are missing.

**Non-Goals:**
- Speaker diarization or speaker-turn labeling.
- Word-level alignment beyond the span granularity available from the chosen transcript backend.
- Cloud transcription services or mandatory remote dependencies.
- Full dialogue-aware story assembly; this change only establishes transcript support and speech-aware fallback.

## Decisions

### 1. Introduce a transcript provider factory for production runs

The process path will construct a transcript provider explicitly instead of relying on callers to inject one.

- `auto`: use a supported local provider when dependencies are available
- `disabled`: force transcript-free operation
- explicit backend name: request a specific local backend and fall back deterministically if it cannot start

Why:
- The current production path never opts into transcript extraction.
- A factory centralizes capability checks, config parsing, and runtime reporting.

Alternatives considered:
- Instantiate `FasterWhisperAdapter` directly inside `analyze_assets()`: rejected because it hides runtime choice and makes testing/config harder.
- Fail the run when transcript tooling is unavailable: rejected because transcript-free workflows must remain first-class.

### 2. Keep transcript extraction optional and local-only

Transcript extraction will remain a best-effort local capability, not a required step.

Why:
- Local-first and deterministic fallback are product constraints.
- Silent footage and non-speech footage must not pay a transcript dependency cost.

Alternatives considered:
- Require transcript extraction whenever `asset.has_speech` is true: rejected because audio presence is not the same as transcript availability and would make process reliability worse.

### 3. Add speech-aware fallback classification when transcript text is missing

Scoring and analysis-mode selection will no longer depend solely on `transcript_excerpt.strip()`. When transcript text is unavailable, clips with strong speech evidence will be allowed to enter a speech-aware fallback path.

The fallback should use signals already available in the analyzer:
- `asset.has_speech`
- `speech_ratio`
- `audio_energy`
- optional transcript-provider status for the asset or segment

Why:
- The current scoring rule demotes obviously spoken clips to visual coverage when transcripts are missing.
- The product should degrade gracefully, not collapse to the wrong modality.

Alternatives considered:
- Leave speech mode transcript-only: rejected because it reproduces the current failure.
- Treat every `has_speech` asset as speech: rejected because ambient audio and mixed clips would be over-promoted.

### 4. Persist transcript runtime status in generated artifacts

`generated/project.json`, process summary output, and desktop process feedback should report whether transcript support was:
- enabled and active
- enabled but unavailable
- disabled by configuration
- partially available with fallback applied

Why:
- The user needs to understand why a “speech test clip” was or was not processed as speech.
- This is necessary for debugging and for future review-facing provenance.

Alternatives considered:
- Only log transcript status to stderr: rejected because it would disappear after the run and would not be inspectable in generated state.

### 5. Use `faster-whisper` as the first supported local backend

The existing adapter already targets `faster_whisper`, so the first implementation should formalize that path instead of adding a new transcription backend.

Why:
- Lowest integration cost.
- The repository already contains the adapter shape and range model.

Alternatives considered:
- Add multiple backends now: rejected as unnecessary scope expansion.

### 6. Add a short transcript probe before full transcription on borderline assets

The shipped implementation now distinguishes between:
- assets that are strong enough to justify full transcription immediately
- assets that are clearly not worth a transcript pass
- borderline assets that should first receive a short targeted probe over the loudest windows

The probe uses cheap audio windows to build a short list of clip ranges, asks the local transcript backend for text only in those ranges, and promotes the asset into the full transcript pass only if real text is detected.

Why:
- The first production transcript implementation materially increased process startup and per-asset analysis time.
- Most of that cost came from transcribing weak or low-value assets that never yielded useful transcript excerpts downstream.
- A probe preserves transcript-backed analysis for real spoken clips while avoiding unnecessary full Whisper runs on weak candidates.

Alternatives considered:
- Full transcription for every asset with audio: rejected because the benchmark cost was too high.
- Pure RMS-based skip without probe: rejected because it dropped useful transcript excerpts on borderline spoken clips.

## Risks / Trade-offs

- **[Transcript dependency increases setup friction]** → Keep transcript support optional, document install flow clearly, and expose explicit disabled/unavailable status.
- **[Speech-aware fallback misclassifies noisy clips as spoken]** → Gate fallback on combined speech signals rather than `has_speech` alone, and preserve deterministic review metadata.
- **[Transcript extraction increases run time]** → Make it configurable, cache transcript spans per asset when possible, and use selective targeting plus a short probe before full transcription on borderline assets.
- **[Transcript spans disagree with scene/audio refinement]** → Treat transcript evidence as one refinement input, not an unconditional override.
- **[Desktop settings become more complex]** → Put transcript controls in advanced settings and make the default `auto` behavior explicit.

## Migration Plan

1. Add transcript runtime configuration and a provider factory in the analyzer.
2. Wire transcript provider creation into the production process path and persist transcript runtime status in generated artifacts.
3. Update scoring and analysis-mode selection to allow speech-aware fallback when transcript text is missing.
4. Surface transcript configuration and runtime availability in the desktop app.
5. Add selective transcript probing and runtime reporting for targeted/probed/rejected assets.
6. Update docs and verify transcript-enabled and transcript-disabled runs.

Rollback:
- Set transcript support to `disabled` and the analyzer returns to transcript-free behavior without changing export or review data shape beyond empty transcript/runtime fields.

## Open Questions

- Which `faster-whisper` model size should be the default for local runs: `small`, `base`, or another tier?
- Should transcript spans be persisted directly in `generated/project.json`, or should only excerpts and runtime summaries be stored for now?
- Should speech-aware fallback alter only scoring mode, or should it also affect timeline labeling and notes when transcript text is missing?
