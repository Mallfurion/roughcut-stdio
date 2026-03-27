## 1. Override Persistence And Resolved Project Loading

- [x] 1.1 Add desktop-backend persistence for per-project best-take override intent and ignore stale override entries when the active generated project changes.
- [x] 1.2 Add a resolved-project loading path that merges baseline generated project data with stored overrides before returning review state to the desktop app.
- [x] 1.3 Add desktop commands for promoting a segment to the active best take for its asset, clearing that asset's active best take, and clearing that asset's override.

## 2. Analyzer-Side Timeline Rebuild

- [x] 2.1 Add analyzer/service helper logic that applies asset-level best-take overrides, including explicit cleared-selection state, to loaded project data without rerunning media processing.
- [x] 2.2 Rebuild active `take_recommendations` and `timeline.items` from the override-adjusted selection set using the existing story-assembly path.
- [x] 2.3 Preserve review transparency by exposing whether the active selected take is analyzer-chosen, editor-overridden, or editor-cleared.

## 3. Desktop Review Interaction

- [x] 3.1 Add review-surface actions to mark a candidate segment as the active best take, clear the active best take for a clip, and clear an existing override.
- [x] 3.2 Update review cards and timeline preview to show override state and refreshed active timeline membership after each change.
- [x] 3.3 Keep analyzer scores, rank context, and sequence rationale visible after an override is applied.

## 4. Export And Verification

- [x] 4.1 Update desktop export so it operates on the same override-resolved timeline state shown in review.
- [x] 4.2 Add automated coverage for resolved-project loading, override application, timeline rebuild, and override-aware export behavior.
- [x] 4.3 Update review/export documentation or operator notes to describe best-take override behavior and its current per-asset scope.
