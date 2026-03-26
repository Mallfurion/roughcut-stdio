## Why

The current analyzer commits too early to raw peak- or scene-derived windows, so downstream scoring and AI analysis operate on segments that are often padded, truncated, or misaligned with the real start and end of a usable moment. Before adding more semantic intelligence, the pipeline needs a deterministic boundary-refinement stage that produces better candidate segments from the structure already available locally.

## What Changes

- Treat low-cost candidate windows as seed regions rather than final segments.
- Add deterministic boundary refinement that snaps, extends, or trims seed regions using transcript spans, audio gaps and transitions, scene boundaries, and bounded duration rules.
- Add a refinement strategy label and confidence score for each refined segment.
- Persist minimal boundary provenance in generated project state so downstream stages can see how a refined segment was formed.
- Keep the legacy candidate path behind a rollout flag until parity is verified.

## Capabilities

### New Capabilities
- `context-complete-segmentation`: Deterministically refine seed regions into better-bounded candidate segments before final scoring.

### Modified Capabilities
- `deterministic-screening`: Candidate generation changes from direct candidate windows to a seed-and-refine flow.

## Impact

- Analyzer core in `services/analyzer/app/prefilter.py`, `analysis.py`, and `domain.py`
- Transcript adapter interface in `services/analyzer/app/analysis.py`
- Generated project schema in `generated/project.json`
- Unit and integration tests for segmentation behavior
