## Context

`runtime-performance-optimization` reduces later-stage waste in semantic validation, evidence preparation, and benchmark reporting. After that slice, the largest remaining cold-run cost is still before VLM analysis begins: the deterministic screening path repeatedly decodes the same media to sample grayscale frames, compute audio windows, and rediscover scene or screening artifacts on every run.

This follow-up targets the deterministic front half of the analyzer without changing the editorial contract. It keeps the workflow local-first, preserves deterministic fallback for source-only and transcript-free footage, and avoids moving any Resolve-critical behavior into model-only paths.

## Goals / Non-Goals

**Goals:**
- Reduce cold-run cost in the deterministic screening path before shortlist narrowing.
- Replace per-timestamp frame extraction with batched frame sampling that preserves the same sampled timestamps and downstream metrics as closely as practical.
- Consolidate audio screening so silence, RMS energy, transcript targeting, and seed generation can share one extracted summary instead of rescanning the asset.
- Persist reusable deterministic preprocessing artifacts for compatible assets and configurations, and rebuild them when they are stale or incompatible.
- Extend benchmark and process reporting so deterministic preprocessing cache warmth is distinguishable from AI cache warmth.

**Non-Goals:**
- Changing semantic-validation budgeting, evidence reuse for shortlisted segments, or MLX runtime reporting already covered by `runtime-performance-optimization`.
- Changing editorial scoring heuristics, story-assembly behavior, or VLM selection policy.
- Generating proxies or introducing a new external media-decoding dependency beyond the existing local toolchain.
- Replacing transcript extraction with a new provider or making transcript support mandatory for screening.
- Batching CLIP embedding work, parallelizing media discovery or the full per-asset analysis loop, or redesigning the current two-stage dedup strategy; those remain later optimization candidates after deterministic prefilter throughput is improved.

## Decisions

### 1. Batch frame extraction per asset instead of per sampled timestamp

Prefilter frame sampling will move away from spawning one `ffmpeg` process per sampled timestamp. The design will favor one bounded extraction plan per asset, or a very small bounded set of extraction passes, that yields all requested grayscale sample frames in timestamp order for downstream metric computation.

Rationale:
- The current per-timestamp extraction strategy pays repeated process-start and decoder-seek overhead before the pipeline narrows candidates at all.
- The analyzer only needs a small, deterministic sample grid per asset, which makes batching practical without changing the editorial contract.

Alternatives considered:
- Keep per-timestamp extraction and rely only on later AI-stage optimizations. Rejected because deterministic screening still dominates cold-path decode work on larger datasets.
- Replace `ffmpeg` with a new Python-native decode stack. Rejected because it would add new runtime surface area and dependency risk without first exhausting the existing local toolchain.

### 2. Consolidate audio screening into one shared asset summary

Deterministic audio screening will produce a shared per-asset summary that can answer silence and RMS-energy questions for transcript gating, transcript probing, and audio-seed generation without rescanning the media separately for each concern. The implementation may still use multiple filters internally if needed, but the analyzer should treat the result as one bounded audio-screening pass.

Rationale:
- The current pipeline pays more than once to derive low-cost audio structure before any shortlist narrowing happens.
- Transcript targeting, probe selection, and seed generation all consume overlapping audio facts and should be able to share them.

Alternatives considered:
- Keep separate silence and RMS passes for simpler code. Rejected because the duplicated media scan cost is paid on every cold run.
- Drop silence detection entirely and infer everything from RMS windows. Rejected because silence intervals still provide useful deterministic structure and gating clarity.

### 3. Persist deterministic preprocessing artifacts with compatibility checks

Scene boundaries, sampled frame signals, and sampled audio signals will be persisted as reusable deterministic preprocessing artifacts when `artifacts_root` is available. Reuse will require a compatibility key derived from the asset identity and any screening configuration that materially changes the produced artifacts. Missing, stale, or incompatible artifacts will be rebuilt automatically.

Rationale:
- Repeat runs on the same footage currently pay the same deterministic screening cost even when nothing about the source media or relevant config changed.
- Deterministic preprocessing is a good cache target because it is reviewable, bounded, and not dependent on remote services.

Alternatives considered:
- Cache only frame or audio signals. Rejected because the same compatibility and warm/cold reporting work is needed either way, and scene/frame/audio artifacts are naturally reused together.
- Cache forever based only on path name. Rejected because media updates, proxy changes, and config changes would make stale reuse unsafe.

### 4. Treat deterministic preprocessing warmth as distinct from AI warmth

Benchmark and process reporting will distinguish deterministic preprocessing reuse from AI cache reuse. A warm preprocessing run should not look like a pure AI speedup, and a cold deterministic front half should remain visible even when AI outputs are cached.

Rationale:
- Without separate counters, runtime comparisons can hide where the real savings came from.
- The previous change already improves AI-path truthfulness; this follow-up should do the same for the deterministic front half.

Alternatives considered:
- Collapse all cache reuse into one generic cache flag. Rejected because it would make the next optimization round less diagnosable.

## Risks / Trade-offs

- [Batched frame extraction may produce slightly different decoded frames than repeated timestamp seeks] -> Preserve the same target timestamps, keep deterministic fallback available, and cover equivalence-sensitive cases with regression tests.
- [Preprocessing cache invalidation may become too loose or too strict] -> Key reuse to asset identity plus relevant screening config and add explicit rebuild behavior for stale artifacts.
- [Consolidated audio screening can make the prefilter code harder to follow] -> Keep the shared audio summary format explicit and route all consumers through the same accessor path.
- [Warm preprocessing runs may mask lingering AI costs if reporting is too coarse] -> Preserve deterministic preprocessing counters separately from AI cache counters in benchmarks and summaries.

## Migration Plan

1. Introduce compatibility keys and artifact formats for reusable deterministic preprocessing outputs.
2. Replace per-timestamp frame extraction with a batched sampling path and validate that downstream deterministic metrics remain stable.
3. Consolidate audio screening into one shared per-asset summary and route transcript gating and seed generation through it.
4. Extend benchmark and process reporting with deterministic preprocessing warm/cold context.
5. Re-run cold and warm process comparisons on the same dataset to confirm that deterministic preprocessing reuse explains the expected runtime delta.

## Open Questions

- Should scene-detection outputs be cached with the same lifecycle as frame/audio screening artifacts, or should they remain independently rebuildable?
- How strict should compatibility keys be around proxy-path changes, file metadata changes, and screening-config versioning?
- After deterministic prefilter throughput improves, should a later change prioritize media-discovery parallelism, asset-level front-half parallelism, CLIP batching, or dedup-pass consolidation next?
