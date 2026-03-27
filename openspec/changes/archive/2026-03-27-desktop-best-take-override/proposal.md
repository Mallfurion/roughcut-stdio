## Why

The desktop review flow currently lets the editor inspect analyzer recommendations, but it does not let the editor correct them. That breaks the product's "editor decides" promise at the exact point where the editor has enough context to pick a better segment and expect the timeline and export to follow that choice.

## What Changes

- Add a desktop review action that lets the editor promote a candidate segment to the active best take for its source asset.
- Add a desktop review action that lets the editor clear the currently selected best take for an asset so the clip drops out of the active timeline until another take is promoted or analyzer state is restored.
- Persist editor best-take overrides locally so the active review timeline survives refreshes and export within the same generated project.
- Rebuild the active rough timeline after an override using the existing story-assembly logic instead of leaving the desktop UI in a display-only state.
- Expose override state in review so the editor can distinguish analyzer-selected takes, manually promoted takes, and editor-cleared selections, and clear an override when needed.
- Ensure Resolve export uses the same active timeline state shown in desktop review when overrides exist.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-workflow`: The desktop app must support local editor take overrides as part of the review-to-export workflow.
- `review-workspace`: The review surface must let the editor promote a segment, show override state, and refresh the active timeline view accordingly.
- `story-assembly`: Timeline assembly must rebuild from the final editor-adjusted selected takes rather than analyzer-selected winners only.
- `resolve-export`: Desktop export must operate on the active override-resolved timeline state, not only the raw generated analyzer output.

## Impact

- `apps/desktop/src` results-step rendering, event handling, and review presentation
- `apps/desktop/src-tauri` command surface and local override persistence
- analyzer service helpers for applying overrides and rebuilding timeline state without rerunning processing
- active project loading and export orchestration for override-aware timeline state
