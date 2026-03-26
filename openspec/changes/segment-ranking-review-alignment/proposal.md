## Why

The analyzer already computes final take selection from a real ranking path, but the desktop review surface does not expose that path coherently. `best_take` is decided from `score_technical`, `score_semantic`, `score_story`, and `score_total`, plus threshold and per-asset selection rules, while the current segment cards mainly show `prefilter.score`, optional `clip_score`, and AI summary text.

That mismatch creates a trust gap. An editor can see that a segment was analyzed, but not why it won, why it lost, how far behind the winner it was, or whether it was skipped before VLM analysis because of shortlisting, deduplication, CLIP gating, or budget capping. The data is partly present in `generated/project.json`, but it is fragmented and the desktop app does not join it into a review-oriented explanation.

This change makes the current recommendation path legible before any future ranking overhaul. The goal is not to change how segments are selected yet. The goal is to show compelling, accurate review information about what was analyzed and what was calculated for each segment.

## What Changes

- Extend review-facing recommendation metadata for every candidate segment so the desktop app can show recommendation outcome, per-asset rank, score gap to the winner, and aligned score explanations.
- Surface the existing scoring breakdown in the desktop review workspace: total score plus technical, semantic, and story components.
- Add analyzer-authored score-driver summaries that use the same scoring formula the selector uses, instead of generic selection copy.
- Make the desktop segment cards join candidate-segment analysis data with take-recommendation ranking data so each card explains both:
  - what analysis happened
  - what recommendation calculation happened
- Show analysis-path status clearly for each segment, including shortlist state, deduplication, CLIP gate, VLM budget cap, evidence coverage, and provider path.
- Distinguish best takes, alternates, backups, and blocked segments in the desktop review language and presentation.
- Keep selection logic and Resolve export semantics unchanged in this change; this is an explainability and review-alignment change first.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `deterministic-screening`: recommendation output becomes review-oriented by persisting ranking status, score breakdown context, and selection explanations for every candidate segment.
- `ai-segment-understanding`: persisted per-segment analysis state becomes explicit enough for the review UI to show what was and was not analyzed.
- `review-workspace`: the desktop review surface shows recommendation outcome, score breakdown, score drivers, and analysis-path details together on each segment card.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/scoring.py`
  - `services/analyzer/app/domain.py`
  - `apps/desktop/src/main.ts`
  - `apps/desktop/src/styles.css`
- Affected outputs:
  - `generated/project.json`
  - desktop review presentation of candidate segments and recommended takes
- Dependencies and systems:
  - current deterministic score formula and per-asset selection thresholds
  - existing prefilter, CLIP, deduplication, and VLM gating metadata
  - current desktop-generated-project loading flow
