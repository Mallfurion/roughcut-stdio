## 1. Deterministic Preprocessing Cache

- [ ] 1.1 Define compatibility keys and persisted artifact formats for reusable scene-boundary, frame-signal, and audio-signal preprocessing outputs.
- [ ] 1.2 Add load, validate, rebuild, and write paths for deterministic preprocessing artifacts when `artifacts_root` is available.
- [ ] 1.3 Add analyzer tests covering cache hit, cache miss, and stale-or-incompatible rebuild behavior.

## 2. Batched Frame Sampling

- [ ] 2.1 Replace per-timestamp grayscale frame extraction with a batched or otherwise bounded per-asset extraction path that preserves the current sample timestamps.
- [ ] 2.2 Keep deterministic fallback behavior intact when batched extraction fails or local runtime dependencies are unavailable.
- [ ] 2.3 Add regression tests that cover sampled-frame ordering, deterministic metric stability, and fallback behavior for the new extraction path.

## 3. Shared Audio Screening

- [ ] 3.1 Consolidate deterministic audio screening so silence intervals, RMS windows, transcript targeting, transcript probing, and audio-seed generation can consume one shared per-asset summary.
- [ ] 3.2 Remove avoidable duplicate media scans from the current audio-screening path while preserving silent-footage and transcript-free behavior.
- [ ] 3.3 Add regression tests for shared audio-summary generation, transcript-gating decisions, and silent-asset fallback.

## 4. Benchmarking, Docs, And Validation

- [ ] 4.1 Extend benchmark artifacts and process summaries with deterministic preprocessing cache warmth, asset-level reuse counts, and any front-half screening activity needed to compare runs.
- [ ] 4.2 Update runtime-related docs and examples for deterministic preprocessing cache behavior, warm-vs-cold interpretation, and the relationship to AI cache reporting.
- [ ] 4.3 Run targeted validation with `python3 -m unittest discover services/analyzer/tests -v` or focused analyzer test subsets plus at least one cold/warm benchmark comparison on the same dataset.
