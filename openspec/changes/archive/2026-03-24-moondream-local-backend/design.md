## Context

The repository already has a provider abstraction for AI segment understanding in `services/analyzer/app/ai.py`. Today that abstraction supports:

- `deterministic`
- `lmstudio`

The current architecture already has the right high-level structure for efficient local vision analysis:

- cheap visual prefiltering
- shortlist construction
- stitched contact-sheet generation
- late-stage VLM analysis over shortlisted segments
- persistent generated project state
- deterministic fallback

Because of that, this change should not redesign the screening pipeline. It should only add a new direct local backend that plugs into the existing VLM refinement stage.

Constraints:

- LM Studio support must remain available
- deterministic fallback must remain available
- `npm run setup`, `npm run check:ai`, and `npm run process` should remain the main workflow
- model loading should happen once per process, not once per segment
- setup should support offline reuse after the initial model download
- the implementation should be explicit about model cache location and device selection

## Goals / Non-Goals

**Goals:**

- Add a first-class `moondream-local` backend for direct in-process inference.
- Make `npm run setup` capable of downloading and preparing the configured Moondream model.
- Make `npm run check:ai` validate the embedded backend rather than just HTTP reachability.
- Reuse the current shortlist/contact-sheet pipeline instead of introducing a new image-analysis path.
- Keep output schema and fallback semantics compatible with the existing app and review UI.

**Non-Goals:**

- Remove LM Studio support in this change.
- Change the scoring-first architecture or prefilter logic.
- Introduce cloud inference.
- Introduce model fine-tuning or training.
- Redesign the web app around the new backend.

## Decisions

### 1. Add Moondream as a new provider, not a replacement

The AI provider configuration should gain a new provider value:

- `deterministic`
- `lmstudio`
- `moondream-local`

This keeps migration risk low and allows benchmarking or fallback between providers.

Alternative considered:
- Replace LM Studio immediately.

Why rejected:
- The current repo already supports LM Studio, and keeping it available makes the transition safer while preserving user choice.

### 2. Integrate Moondream directly in-process via Python

The new backend should run inside the analyzer process rather than via an external server. The analyzer should load the model once, keep it resident for the duration of `process`, and analyze shortlisted contact-sheet images directly.

Alternative considered:
- Use Moondream Station as an HTTP service.

Why rejected:
- That still leaves the project dependent on an external runtime. The user goal here is to tighten the app into a more self-contained local product.

### 3. Use setup-time bootstrap for model preparation

`npm run setup` should be able to:

- install the required Python dependencies
- download the configured model and revision
- warm or validate the local cache

This should be configurable so advanced or CI environments can skip automatic download if desired.

Alternative considered:
- Download on first `process` run only.

Why rejected:
- That makes the first real processing run slower and more failure-prone, and it makes the runtime story less predictable.

### 4. Keep current shortlist/contact-sheet semantics

The Moondream backend should consume the same inputs currently used by the LM Studio refinement path:

- shortlisted segments only
- stitched contact-sheet image when available
- keyframe fallback when needed
- narrow structured prompt focused on usefulness, subject, motion, clarity, and interest

Alternative considered:
- Add a separate Moondream-specific segmentation path.

Why rejected:
- That would fragment the architecture and make provider comparison difficult.

### 5. Extend health checks to cover backend readiness, not just availability

`npm run check:ai` should report backend-specific readiness:

- deterministic: always ready
- lmstudio: HTTP reachability and model listing
- moondream-local: imports, weights available, model loadable, smoke inference path healthy

Alternative considered:
- Keep `check:ai` LM Studio-specific and add a different command for Moondream.

Why rejected:
- The project already has `check:ai`; it should become provider-aware instead of multiplying commands.

## Risks / Trade-offs

- [Setup becomes heavier] -> Mitigation: provide a skip-download flag and make model cache location explicit.
- [Python dependency surface grows] -> Mitigation: isolate Moondream-specific requirements and document them clearly.
- [Model load time may be noticeable] -> Mitigation: load once per process and report warm-up time in logs.
- [Device/runtime behavior may vary across machines] -> Mitigation: support explicit device selection and record the effective device in process logs.
- [Direct integration may require model-specific response handling] -> Mitigation: keep the existing `SegmentUnderstanding` normalization boundary and provider-specific adapter class.

## Migration Plan

1. Add provider config support for `moondream-local`.
2. Add a Moondream runtime adapter that loads the model once and performs direct image analysis.
3. Add a model bootstrap script and wire it into `npm run setup`.
4. Extend `npm run check:ai` for provider-aware Moondream validation.
5. Update process logs and summaries with effective backend, device, cache path, and live/cached/fallback counters.
6. Update docs and examples while keeping LM Studio instructions available.

## Open Questions

- Which Moondream model ID and revision should be the default in this repository?
- Should setup download the default model automatically, or prompt via env opt-in/out behavior only?
- Should model artifacts live under `models/`, `.cache/`, or a configurable env path outside the repo?
