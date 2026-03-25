## Why

The repository now has a screening-first pipeline: cheap visual prefiltering narrows each asset to a small shortlist, and optional VLM analysis runs only after that shortlist exists. However, final recommendation still comes from deterministic selection rules rather than an editorial comparison of the shortlisted regions. That means the product still does not fully deliver on the promise of surfacing the strongest shots in a way that feels trustworthy and visually grounded.

Phase 2 should make segment recommendation trustworthy by ranking the prefilter shortlist inside each clip, using the VLM as a late refinement step rather than an early screening tool, while keeping deterministic guardrails for safety, cost control, and fallback.

## What Changes

- Add AI-assisted intra-clip ranking so prefilter-shortlisted candidate segments from the same asset can be compared directly instead of only scored independently.
- Make per-asset batched ranking the default ranking strategy so the shortlisted regions from one source clip are compared in a single provider pass whenever possible.
- Add keep/maybe/reject recommendation outcomes and visible alternates for each asset.
- Add redundancy detection for near-duplicate candidate segments within the same clip.
- Replace current deterministic best-take selection as the authoritative recommendation layer with AI-informed ranking backed by deterministic tie-breaks, shortlist limits, and fallback behavior.
- Keep the VLM prompt narrow and editorially focused: subject presence, motion usefulness, clarity, composition, visual interest, and overall usability as a selected segment.
- Keep provider support provider-neutral across `lmstudio` and `mlx-vlm-local`, with deterministic fallback when neither provider can be used.
- Expand the review UI to show why one segment won, what alternatives remain available, and why other segments were rejected or downgraded.
- Preserve the current `setup / process / view / export` workflow while changing the recommendation logic underneath it.

## Capabilities

### New Capabilities
- `ai-segment-ranking`: batched comparative ranking of shortlist segments, redundancy detection, recommendation outcomes, and explainable per-clip winners and alternates.

### Modified Capabilities
- `deterministic-screening`: keep deterministic scoring as a screening, shortlist, and fallback layer while shifting final recommendation authority to AI-assisted ranking of shortlisted regions.
- `review-workspace`: extend the UI from passive recommendation display to explanation of winner/alternate/rejected segment outcomes and ranking rationale.
- `ai-segment-understanding`: extend structured segment records to include comparison and ranking outputs that can drive final selection after the screening stage.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/ai.py`
  - `services/analyzer/app/domain.py`
  - `services/analyzer/app/scoring.py`
  - desktop review UI under `apps/desktop`
- Affected outputs:
  - `generated/project.json`
  - recommendation state shown in the desktop review workflow
- Dependencies and systems:
  - batched per-asset VLM request strategy
  - deterministic fallback path
  - prefilter shortlist construction
  - local runtime cost controls introduced in Phase 1.5 and the screening-first pipeline
  - provider support for both `lmstudio` and `mlx-vlm-local`
