## Why

The repository can already emit a rough timeline, but it is still assembled from deterministic ordering rules and presented mostly as a static preview of selected segments. The product manifesto calls for a tool that can assemble shortlisted strong moments into a rough cut the editor can inspect, adjust, and carry into Resolve.

Phase 3 should turn selected segments into an editable first-pass rough sequence with clearer story-role intent, preview-oriented review, and export that reflects the same approved timeline state the editor sees in the app.

## What Changes

- Add cross-clip story-role assignment for shortlisted segments so they can function as opener, bridge, detail, development beat, payoff, or outro.
- Add sequence assembly logic that builds one or more rough-cut variants from shortlisted segments instead of relying primarily on source order.
- Expand the review experience from static timeline inspection to timeline-oriented preview, reorder, trim, and approval of the assembled rough cut.
- Make the browser preview and Resolve export operate from the same approved timeline state.
- Keep chronology as the default assembly heuristic while allowing role-aware sequencing on top of the existing shortlist.
- Preserve deterministic export-safe trim bounds and source reference stability while changing how timeline order is chosen.

## Capabilities

### New Capabilities
- `story-assembly`: story-role assignment, rough-cut variant construction, and approved timeline-state management for shortlisted segments.

### Modified Capabilities
- `review-workspace`: extend the web app from generated-state inspection into timeline preview, reordering, trimming, and approval workflow.
- `resolve-export`: export the editor-approved timeline state rather than only the initially generated deterministic sequence.
- `processing-workflow`: incorporate story-assembly outputs into the normal `process / view / export` flow without adding a separate orchestration model.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/domain.py`
  - `services/analyzer/app/fcpxml.py`
  - `apps/web/app/page.tsx`
  - timeline-related UI and API routes
- Affected outputs:
  - `generated/project.json`
  - approved timeline state
  - `generated/timeline.fcpxml`
- Dependencies and systems:
  - browser timeline preview
  - sequence-assembly heuristics or planner prompts
  - export path that must stay Resolve-compatible
