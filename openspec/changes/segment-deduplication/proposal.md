## Why

The current pipeline can generate multiple candidate segments from the same asset that cover nearly identical visual content. This happens because candidates are built from two independent sources — PySceneDetect boundaries and visual score peak windows — that can overlap semantically even when they do not overlap temporally by the current 90% threshold. A scene with a static wide shot held for 12 seconds, for example, may produce three candidate windows with different start times but essentially the same visual content. All three can pass the prefilter shortlist, all three can reach the VLM stage, and any two of them can end up in the final timeline as adjacent items with identical descriptions.

Deduplication is a quality problem before it is a compute problem. The editor should see the best representative of each distinct moment, not three variants of the same shot. Removing near-duplicate candidates before scoring and VLM targeting directly improves the signal-to-noise ratio of the review workspace and the relevance of the final shortlist.

The first implementation should have no new model dependencies. Grayscale frame histograms — built from the same low-resolution frames already extracted during prefilter sampling — are sufficient to detect visually near-identical segments within the same asset at negligible cost. CLIP-based embedding similarity can be layered on later as an optional upgrade for cross-asset deduplication and for richer semantic grouping.

## What Changes

- Add a deduplication pass that runs after prefilter scoring and before VLM targeting, operating over the candidate segment set for each asset.
- Implement histogram-based visual similarity using the grayscale frames already extracted during `sample_asset_signals()`: compute a coarse luminance histogram per segment from its representative frames, compare histograms across candidates within the same asset using histogram intersection, and group candidates whose similarity exceeds a configurable threshold (default: 0.85).
- For each duplicate group, retain the single highest-scoring candidate and mark the rest as `deduplicated`. Store the group membership and the reason for elimination in each eliminated segment's `prefilter` record.
- Deduplicated segments do not reach the shortlist, do not receive keyframe extraction, and do not count against `max_segments_per_asset`.
- Add an optional `TIMELINE_DEDUP_THRESHOLD` environment variable to adjust the similarity threshold for workflows with more or less visual variation between clips.
- Add CLIP-based embedding similarity as a future-compatible extension point: when `TIMELINE_AI_CLIP_ENABLED=true` is set and the `open-clip-torch` package is available, use CLIP keyframe embeddings instead of histogram comparison for richer semantic deduplication. The histogram path remains the default.
- Extend process reporting to show per-asset deduplication statistics: total candidates generated, candidates deduplicated, and candidates forwarded to the shortlist stage.

## Capabilities

### New Capabilities
- `segment-deduplication`: histogram-based near-duplicate detection and suppression within each asset's candidate set, with an optional CLIP-backed upgrade path.

### Modified Capabilities
- `vision-prefilter-pipeline`: insert deduplication as a distinct named step after prefilter scoring and before shortlist selection and VLM targeting.
- `deterministic-screening`: prefilter shortlist and scoring now operate over a deduplicated candidate set, improving shortlist quality without changing the scoring logic itself.
- `processing-workflow`: add per-asset deduplication statistics to process-time reporting.

## Impact

- Affected code:
  - `services/analyzer/app/prefilter.py`
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/domain.py`
- Affected outputs:
  - `generated/project.json` — eliminated segments carry `prefilter.deduplicated=true` and `prefilter.dedup_group_id` in their prefilter record
  - `generated/process.log` — per-asset deduplication summary
- Dependencies and systems:
  - grayscale frames already extracted by `sample_asset_signals()` — no new extraction cost
  - `TIMELINE_DEDUP_THRESHOLD` environment variable (optional, default 0.85)
  - `open-clip-torch` as optional dependency for the CLIP upgrade path — not required for baseline
