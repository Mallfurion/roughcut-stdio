## Why

After the `audio-signal-layer` and `segment-deduplication` changes, the prefilter stage will produce a smaller, cleaner shortlist. But the gap between that shortlist and the VLM stage is still narrow: the shortlist is ranked by visual and audio feature signals that measure sharpness, motion, stability, and energy, but not editorial or semantic quality. A sharp, stable, non-duplicate segment is still not necessarily an interesting shot. The pipeline currently bridges this gap by sending the shortlist directly to the VLM, which means the VLM is still being used to answer a question that a cheaper tool could partially answer first.

CLIP (Contrastive Language-Image Pretraining) can score a keyframe against a natural-language query in under 100ms on CPU and under 10ms on GPU, making it roughly two orders of magnitude cheaper than a VLM call. Used at the right point in the pipeline, it serves as a semantic Tier 1 filter: after cheap visual signals have removed blurry, static, and duplicate footage, CLIP can further separate visually coherent shots that match editorial criteria from those that do not, before a VLM is asked to reason about any of them.

At the same time, the pipeline currently has no hard budget constraint on VLM usage across the full run. `max_segments_per_asset` limits per-clip VLM targets, but a project with 40 assets still sends up to `40 × max_segments_per_asset` segments to the VLM. Adding a global budget cap — expressed as a percentage of all candidates — gives the operator clear cost control and makes VLM targeting proportional to footage volume rather than clip count.

## What Changes

- Add CLIP as an optional Tier 1 semantic scoring step that runs between the prefilter shortlist and VLM targeting, enabled via `TIMELINE_AI_CLIP_ENABLED=true`.
- When enabled, run CLIP inference on the contact-sheet or first keyframe of each shortlisted segment against a small fixed prompt set: positive anchors such as `"cinematic shot"`, `"sharp focus and good composition"`, `"interesting moment"`, and `"subject clearly visible"`, plus negative anchors such as `"blurry or out of focus"` and `"empty scene with no subject"`.
- Compute a `clip_score` per segment as a weighted combination of positive similarities minus negative similarities, normalized to [0, 1]. Persist this as a new field in the prefilter metrics snapshot.
- Use `clip_score` as an additional gate before VLM targeting: segments below a configurable `TIMELINE_AI_CLIP_MIN_SCORE` threshold (default: `0.35`) are skipped for VLM analysis and receive deterministic understanding instead.
- Incorporate `clip_score` into the final scoring system in `scoring.py` as a semantic input alongside the existing visual and audio metrics.
- Add a global VLM budget cap via `TIMELINE_AI_VLM_BUDGET_PCT` (default: `10`). After deduplication and CLIP filtering, enforce that VLM targets across all assets do not exceed this percentage of the total candidate pool. When the cap is binding, the highest-scoring shortlisted segments are prioritised within each asset.
- When `TIMELINE_AI_CLIP_ENABLED` is false or `open-clip-torch` is not installed, the CLIP step is skipped entirely: the pipeline proceeds from prefilter shortlist directly to VLM targeting as it does today, with no change to existing behaviour.
- Extend process reporting to show CLIP coverage: how many shortlisted segments were scored, how many were gated before VLM, what percentage of total candidates reached VLM, and whether the global budget cap was binding.

## Capabilities

### New Capabilities
- `clip-semantic-scoring`: optional CLIP-based semantic quality scoring and VLM pre-gate between the prefilter shortlist and the VLM analysis stage.

### Modified Capabilities
- `vision-prefilter-pipeline`: insert the CLIP scoring step as a named optional stage after shortlist selection, before keyframe extraction and VLM targeting.
- `deterministic-screening`: add `clip_score` as a scoring input alongside prefilter visual and audio metrics when CLIP is enabled.
- `ai-segment-understanding`: strengthen VLM budget discipline with a global percentage cap so VLM targeting scales with footage volume rather than clip count.
- `processing-workflow`: add CLIP coverage and VLM budget utilisation statistics to process-time reporting.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/scoring.py`
  - `services/analyzer/app/domain.py`
  - `services/analyzer/app/ai.py`
- Affected outputs:
  - `generated/project.json` — prefilter metrics snapshot gains `clip_score` field when CLIP is enabled; segments gated by CLIP carry `prefilter.clip_gated=true`
  - `generated/process.log` — CLIP coverage and VLM budget summary
- Dependencies and systems:
  - `open-clip-torch` — optional Python package, not required for baseline pipeline operation
  - `TIMELINE_AI_CLIP_ENABLED` environment variable (default: `false`)
  - `TIMELINE_AI_CLIP_MIN_SCORE` environment variable (default: `0.35`)
  - `TIMELINE_AI_VLM_BUDGET_PCT` environment variable (default: `10`)
  - keyframe extraction must run before CLIP scoring; contact sheets already produced by `build_segment_evidence()` are reused as CLIP inputs
