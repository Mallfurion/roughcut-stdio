## 1. Deterministic Preprocessing Cache

- [x] 1.1 Define compatibility keys and persisted artifact formats for reusable scene-boundary, frame-signal, and audio-signal preprocessing outputs.
- [x] 1.2 Add load, validate, rebuild, and write paths for deterministic preprocessing artifacts when `artifacts_root` is available.
- [x] 1.3 Add analyzer tests covering cache hit, cache miss, and stale-or-incompatible rebuild behavior.

## 2. Batched Frame Sampling

- [x] 2.1 Replace per-timestamp grayscale frame extraction with a batched or otherwise bounded per-asset extraction path that preserves the current sample timestamps.
- [x] 2.2 Keep deterministic fallback behavior intact when batched extraction fails or local runtime dependencies are unavailable.
- [x] 2.3 Add regression tests that cover sampled-frame ordering, deterministic metric stability, and fallback behavior for the new extraction path.

## 3. Shared Audio Screening

- [x] 3.1 Consolidate deterministic audio screening so silence intervals, RMS windows, transcript targeting, transcript probing, and audio-seed generation can consume one shared per-asset summary.
- [x] 3.2 Remove avoidable duplicate media scans from the current audio-screening path while preserving silent-footage and transcript-free behavior.
- [x] 3.3 Add regression tests for shared audio-summary generation, transcript-gating decisions, and silent-asset fallback.

## 4. Benchmarking, Docs, And Validation

- [x] 4.1 Extend benchmark artifacts and process summaries with deterministic preprocessing cache warmth, asset-level reuse counts, and any front-half screening activity needed to compare runs.
- [x] 4.2 Update runtime-related docs and examples for deterministic preprocessing cache behavior, warm-vs-cold interpretation, and the relationship to AI cache reporting.
- [x] 4.3 Run targeted validation with `python3 -m unittest discover services/analyzer/tests -v` or focused analyzer test subsets plus at least one cold/warm benchmark comparison on the same dataset.
