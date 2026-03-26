## Why

Better boundaries are necessary, but they are not sufficient. Even well-bounded segments can still represent only half of a dialogue exchange, one side of an action-reaction pair, or two separate ideas packed into one interval. After deterministic refinement, the pipeline needs an assembly step that turns adjacent refined regions into the narrative units an editor can actually use.

## What Changes

- Add a narrative-unit assembly stage after deterministic boundary refinement.
- Merge adjacent refined regions when continuity evidence indicates they belong to one editorial beat.
- Split refined regions when transcript or structure shows they contain multiple ideas.
- Recalculate segment-level metrics and descriptions on the assembled units before recommendation and timeline assembly.
- Persist merge and split lineage in project state for downstream inspection.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `context-complete-segmentation`: Refined regions are assembled into final narrative units through merge and split operations before scoring.
- `deterministic-screening`: Final candidate segments are produced after narrative assembly rather than immediately after deterministic refinement.

## Impact

- Analyzer core in `services/analyzer/app/analysis.py`, `domain.py`, and scoring integration
- Generated project schema in `generated/project.json`
- Tests for merge/split rules and re-aggregated metrics
