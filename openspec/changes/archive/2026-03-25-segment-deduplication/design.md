## Context

The candidate segment set for a single asset is built from two independent sources: PySceneDetect scene boundaries and visual score peak windows. These sources can produce candidates that are temporally distinct but visually near-identical. A static wide shot held across a scene cut, a slow pan with minimal change between adjacent windows, or any footage where the camera is stationary for several seconds can produce two or three candidates that describe the same visual content. None of the current pipeline stages detect or suppress this redundancy.

The effect compounds across the pipeline. Near-duplicate candidates all pass the prefilter shortlist independently. They all reach keyframe extraction. They all reach the VLM stage. If the VLM provider is not available, the deterministic analyzer runs on all of them and produces near-identical understanding records. In the final timeline, two adjacent items from the same asset may describe the same shot in slightly different words, wasting review attention and editorial runtime.

Deduplication should happen as early as possible — after prefilter scoring has established which candidate is strongest within a group, and before VLM targeting. The data required for deduplication already exists: the grayscale frames extracted during `sample_asset_signals()` are low-resolution representations of the visual content of each timestamp. A coarse luminance histogram per segment, built from those frames, is sufficient to measure visual similarity between candidates in the same asset at negligible additional cost.

The CLIP-based upgrade path is defined in this change but not activated by default. It enables richer semantic grouping — detecting similarity that histogram comparison misses, such as two shots of the same person from different angles — and enables cross-asset deduplication, which histogram comparison cannot do reliably. It requires `open-clip-torch` and is enabled only when `TIMELINE_AI_CLIP_ENABLED=true` is set and the package is installed.

Constraints:

- deduplication must not silently discard segments — eliminated candidates must remain in `generated/project.json` with their deduplication status recorded
- the deduplication step must not affect Resolve export correctness
- silent footage must remain a first-class path — deduplication is purely visual and does not require audio or transcript data
- the `setup -> process -> view -> export` workflow must remain intact
- deterministic fallback must remain available at all times

## Goals / Non-Goals

**Goals:**

- Remove near-duplicate candidates from the VLM target set and the prefilter shortlist before any keyframe extraction or model call.
- Use grayscale frame histograms computed from already-extracted frames as the baseline comparison mechanism, with no new binary dependency and no additional frame extraction.
- Retain the highest-scoring candidate from each duplicate group and mark the rest as deduplicated in the prefilter record.
- Deduplicated candidates must not count against `max_segments_per_asset` in fast mode.
- Expose a configurable similarity threshold via `TIMELINE_DEDUP_THRESHOLD` for tuning without code changes.
- Define a CLIP-backed upgrade path that slots in behind the same interface when `open-clip-torch` is available and enabled.
- Extend process reporting with per-asset deduplication statistics.

**Non-Goals:**

- Cross-asset deduplication in the baseline implementation. The histogram approach is not reliable across different clips with different exposure or color grading. Cross-asset deduplication belongs to the CLIP upgrade path.
- Deduplication based on transcript similarity. That is a separate concern addressed by transcript-aware ranking.
- Any change to the FCPXML export or Resolve handoff.
- Any change to the desktop review workspace in this change.

## Decisions

### 1. Insert deduplication after prefilter scoring and before shortlist selection

Deduplication needs prefilter scores to decide which candidate to keep from each group. Running it before scoring would force an arbitrary tie-break. Running it after shortlist selection would mean redundant candidates have already consumed shortlist slots. The correct position is: score all candidates, then deduplicate, then select the shortlist from the deduplicated set.

Alternative considered:
- Deduplicate before prefilter scoring using timestamps only (overlap ratio).

Why rejected:
- Temporal proximity does not imply visual similarity. Two windows at 3s and 7s in a static shot are not temporally overlapping but are visually identical. The current `dedupe_ranges()` function already handles temporal overlap at 90% threshold; this change targets the complementary case where segments are far apart in time but close in visual content.

### 2. Use luminance histogram intersection as the baseline similarity metric

A coarse luminance histogram (16–32 bins) per segment, computed from the mean of its representative grayscale frames, captures the gross visual character of a segment cheaply. Histogram intersection — `sum(min(H1[i], H2[i]))` normalized to [0, 1] — is a standard, parameter-free measure of histogram similarity. Two segments with the same overall luminance distribution are likely to look similar to an editor.

The comparison is O(N²) over candidates within a single asset. At typical candidate counts per asset (4–10), this is negligible.

Alternative considered:
- Perceptual hash (pHash or dHash) comparison.

Why rejected:
- Perceptual hashes are effective for near-identical images but are sensitive to lighting changes and reframing that an editor would still consider "the same shot". Histogram intersection is more tolerant of small shifts while still catching the static-shot and slow-pan cases this change is primarily targeting.

Alternative considered:
- SSIM (structural similarity) between full frames.

Why rejected:
- SSIM over 64px grayscale frames is cheap but still more expensive than histogram comparison for no material accuracy gain at this resolution and for the problem being solved.

### 3. Keep one candidate per duplicate group — the highest-scoring one

When two or more candidates are grouped as near-duplicates, the candidate with the highest prefilter score is retained as the group representative. All others are marked `deduplicated=true` and assigned a `dedup_group_id` matching the retained candidate's ID.

Alternative considered:
- Keep the temporally earliest candidate in the group.

Why rejected:
- Earliest is not necessarily best. The prefilter score already encodes sharpness, motion, stability, and distinctiveness. Using it as the tie-break is consistent with the rest of the pipeline's screening logic.

### 4. Deduplicated candidates remain in generated project state

Eliminated candidates are not removed from `generated/project.json`. They are preserved with `prefilter.deduplicated=true`, `prefilter.dedup_group_id`, and a `prefilter.selection_reason` that names the retained candidate. This makes the deduplication decision inspectable and preserves the full candidate record for any future tooling that may want to revisit eliminated segments.

Alternative considered:
- Strip deduplicated candidates from the output entirely.

Why rejected:
- Silent discard makes debugging and future review impossible. The pipeline's general principle is that nothing is discarded without a recorded reason.

### 5. Define the CLIP upgrade path behind `TIMELINE_AI_CLIP_ENABLED`

The CLIP-based similarity path uses keyframe embeddings rather than frame histograms. It is more accurate for semantic similarity and enables cross-asset grouping. It requires `open-clip-torch`, which is not a lightweight dependency. The upgrade path is defined now so it can be slotted in cleanly when the `clip-semantic-scoring` change is implemented, without restructuring the deduplication interface.

When `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is available, the deduplication step uses CLIP embedding cosine similarity instead of histogram intersection. The threshold semantics remain the same. When the package is not available, the histogram path is used regardless of the flag value.

Alternative considered:
- Wait until the `clip-semantic-scoring` change and define deduplication there.

Why rejected:
- Deduplication is a prefilter concern that should be in place and tested before CLIP scoring is introduced. Splitting the interface definition from the initial implementation creates a clean seam for the upgrade without blocking this change on CLIP availability.

## Risks / Trade-offs

- [Histogram similarity may group visually distinct segments at the default threshold] → Mitigation: the default threshold of 0.85 is conservative. Test against real footage and adjust if over-grouping is observed. Expose `TIMELINE_DEDUP_THRESHOLD` for per-project tuning.
- [Histogram similarity may fail to group semantically similar segments from different exposures] → Mitigation: this is a known limitation of the baseline approach. The CLIP upgrade path addresses it. Document the limitation.
- [O(N²) comparison adds processing time for assets with many candidates] → Mitigation: at typical candidate counts (4–10 per asset) the cost is negligible. Add a guard to skip deduplication for assets with fewer than 2 candidates.
- [Dedup group ID semantics need to be stable across reruns] → Mitigation: dedup group IDs should be derived from the retained candidate's segment ID, which is already deterministic.

## Migration Plan

1. Add `deduplicated`, `dedup_group_id`, and updated `selection_reason` fields to the `PrefilterDecision` domain model.
2. Implement `compute_segment_histogram()` in `prefilter.py` using the grayscale frames already stored in `FrameSignal` records.
3. Implement `deduplicate_segments()` in `prefilter.py`: compute histograms, compare pairs, group by threshold, retain highest-scoring per group.
4. Insert `deduplicate_segments()` into `analyze_assets()` in `analysis.py` after prefilter scoring and before shortlist selection.
5. Update shortlist selection so deduplicated candidates are excluded from the pool and do not count against `max_segments_per_asset`.
6. Add `TIMELINE_DEDUP_THRESHOLD` environment variable loading to the AI config.
7. Define the CLIP embedding comparison path behind the `TIMELINE_AI_CLIP_ENABLED` flag, with fallback to histogram when the package is unavailable.
8. Extend process reporting with per-asset deduplication statistics.
9. Add tests for histogram computation, similarity grouping, threshold behavior, and fallback for assets with fewer than 2 candidates.
10. Verify the full pipeline produces correct output with and without deduplication.

## Open Questions

- Should deduplication also apply across segments from different assets? The histogram baseline cannot do this reliably, but the CLIP upgrade path could. Should the scope be explicitly stated as intra-asset only for now?
- What is the right default for `TIMELINE_DEDUP_THRESHOLD`? 0.85 is a starting point but should be validated against real footage before being treated as stable.
- Should the number of peak windows generated in `build_prefilter_segments()` be increased now that deduplication will remove redundant candidates, or is the current 2–3 per asset still appropriate?
