## Why

Once segments are refined, merged, split, and sometimes semantically validated, the editor needs to understand why a segment exists in its current form. If provenance remains hidden in logs or internal schema only, the system becomes harder to trust and harder to debug. The review surface needs a bounded, readable explanation of segment formation.

## What Changes

- Persist review-oriented provenance for final candidate segments and recommended takes.
- Expose boundary strategy, confidence, merge/split lineage, and semantic-validation status in the desktop review workspace.
- Keep provenance display concise enough for editors while preserving full source references in project state.
- Avoid changing Resolve export semantics; provenance is explanatory, not editorially destructive.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `context-complete-segmentation`: Final candidate segments persist review-facing provenance about how they were formed.
- `review-workspace`: The desktop review surface displays segment provenance and refinement decisions.

## Impact

- Generated project schema in `generated/project.json`
- Desktop review UI in `apps/desktop`
- Domain serializers and tests for provenance display data
