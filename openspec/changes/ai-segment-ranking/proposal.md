## Why

The repository can already discover candidate segments and attach structured AI understanding, but final recommendation still comes from deterministic placeholder scoring. That means the product does not yet fulfill the core promise of surfacing the strongest segments in a way that feels editorially grounded.

Phase 2 should make segment recommendation trustworthy by replacing scalar heuristic selection with AI-assisted comparative ranking inside each clip while keeping deterministic guardrails for safety and fallback.

## What Changes

- Add AI-assisted intra-clip ranking so shortlisted candidate segments from the same asset can be compared directly instead of only scored independently.
- Add keep/maybe/reject recommendation outcomes and visible alternates for each asset.
- Add redundancy detection for near-duplicate candidate segments within the same clip.
- Replace current deterministic best-take selection as the authoritative recommendation layer with AI-informed ranking backed by deterministic tie-breaks and fallback behavior.
- Expand the review UI to show why one segment won, what alternatives remain available, and why other segments were rejected or downgraded.
- Preserve the current `setup / process / view / export` workflow while changing the recommendation logic underneath it.

## Capabilities

### New Capabilities
- `ai-segment-ranking`: comparative segment ranking, redundancy detection, recommendation outcomes, and explainable per-clip winners and alternates.

### Modified Capabilities
- `deterministic-screening`: replace deterministic-only best-take selection with AI-assisted recommendation logic while retaining deterministic fallback and guardrails.
- `review-workspace`: extend the UI from passive recommendation display to explanation of winner/alternate/rejected segment outcomes and ranking rationale.
- `ai-segment-understanding`: extend structured segment records to include comparison and ranking outputs that can drive final selection.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/ai.py`
  - `services/analyzer/app/domain.py`
  - `services/analyzer/app/scoring.py`
  - `apps/web/app/page.tsx`
  - `apps/web/lib/project.ts`
- Affected outputs:
  - `generated/project.json`
  - recommendation state shown in the web UI
- Dependencies and systems:
  - LM Studio request strategy
  - deterministic fallback path
  - local runtime cost controls introduced in Phase 1.5
