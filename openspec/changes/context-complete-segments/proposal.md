## Why

The current analyzer is good at finding salient snippets, but it still treats those snippets as if they were already usable edit units. That is the real gap: the product needs context-complete narrative beats, not just visually or acoustically interesting windows. This change now serves as the parent roadmap for the segmentation overhaul and is intentionally split into smaller implementation-ready changes.

## What Changes

- Define the target end state: a staged segmentation pipeline that treats low-cost windows as seed regions rather than final candidate segments.
- Split the work into focused child changes:
  - `deterministic-boundary-refinement`
  - `narrative-unit-assembly`
  - `semantic-boundary-validation`
  - `segment-provenance-review`
- Use this parent change to keep the problem statement and architecture coherent while implementation proceeds in smaller units.

## Capabilities

### New Capabilities
- `context-complete-segmentation`: Refine seed regions into editorially usable narrative units using deterministic structure first and selective semantic escalation second.

### Modified Capabilities
- `deterministic-screening`: Candidate generation changes from fixed candidate windows to a seed-and-refine flow that produces context-complete segments before ranking and timeline assembly.
- `ai-segment-understanding`: AI analysis changes to support optional boundary validation on ambiguous segments while preserving deterministic fallback and runtime controls.
- `review-workspace`: Review surfaces must expose segment provenance, boundary decisions, and merge/split reasoning so editors can inspect the refinement pipeline.

## Impact

- Parent roadmap for the segmentation overhaul
- No direct implementation work should start from this change; use the child changes instead
