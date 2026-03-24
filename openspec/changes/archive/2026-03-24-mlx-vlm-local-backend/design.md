## Context

The repository already has the right high-level AI pipeline for efficient local screening:

- cheap prefiltering
- shortlist construction
- stitched contact-sheet generation
- late-stage VLM refinement
- deterministic fallback

What is failing is the choice of embedded runtime. `moondream-local` was added as a direct in-process provider, but in practice it is not a good fit for Apple Silicon in this codebase. The replacement should change the embedded runtime layer while preserving the rest of the pipeline.

Constraints:

- `lmstudio` must remain supported
- deterministic fallback must remain supported
- the default npm workflow must stay `setup -> check:ai -> process -> view -> export`
- the embedded backend should target Apple Silicon explicitly
- the implementation should remove `moondream-local` rather than keeping two embedded backends alive in parallel

## Goals / Non-Goals

**Goals:**

- Replace `moondream-local` with `mlx-vlm-local`.
- Use an Apple-Silicon-optimized embedded runtime.
- Make `Qwen 3.5 0.8B` the default embedded-model target for the local MLX path.
- Update setup and health checks so the embedded runtime is first-class.
- Keep provider-independent project outputs and fallback semantics unchanged.

**Non-Goals:**

- Remove `lmstudio`.
- Change the screening-first architecture.
- Implement AI-driven selection ranking in this change.
- Support non-Apple embedded acceleration as a primary concern.

## Decisions

### 1. Replace the embedded provider instead of accumulating another one

The repository should not keep growing multiple embedded runtimes. `moondream-local` should be removed and replaced by `mlx-vlm-local`.

Why:
- The embedded backend exists to provide a self-contained local path.
- Keeping a broken or unstable embedded provider increases maintenance cost and user confusion.

### 2. Keep LM Studio as the alternative external runtime

`lmstudio` remains useful as a flexible fallback or comparison runtime, especially when users want to try other models without changing the repository-integrated backend.

### 3. Keep the same shortlist/contact-sheet contract

`mlx-vlm-local` should consume the same shortlisted segment evidence as the current AI stage:

- shortlisted segments only
- contact-sheet or keyframe image input
- narrow structured prompt
- normalization into the existing `SegmentUnderstanding` schema

### 4. Make setup and check provider-aware for MLX

`npm run setup` should install MLX/MLX-VLM dependencies and prepare the configured local model. `npm run check:ai` should validate that the MLX backend is usable on the current machine.

### 5. Optimize explicitly for Apple Silicon

The new embedded backend should assume Apple Silicon as its primary runtime target and document that expectation clearly.

## Risks / Trade-offs

- [MLX backend may reduce portability for non-Apple environments] -> Mitigation: keep `deterministic` and `lmstudio` available.
- [Model naming and packaging may differ from current env conventions] -> Mitigation: document the new env vars clearly and remove obsolete Moondream settings.
- [Migration will invalidate some existing local config] -> Mitigation: update `.env.example`, README, and `check:ai` error messages so the migration path is obvious.

## Migration Plan

1. Remove `moondream-local` runtime code and env references.
2. Add `mlx-vlm-local` provider configuration and runtime adapter.
3. Add setup/bootstrap logic for MLX runtime and the default embedded model.
4. Update `check:ai` to validate the MLX backend.
5. Update docs and examples to make `mlx-vlm-local` the recommended embedded path.

## Open Questions

- Which exact MLX model identifier should be the default for the repository’s `Qwen 3.5 0.8B` target?
- Should the MLX backend be treated as supported only on macOS Apple Silicon, with explicit rejection elsewhere?
