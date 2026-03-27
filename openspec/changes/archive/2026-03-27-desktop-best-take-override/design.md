## Context

The current desktop app loads `generated/project.json`, renders `take_recommendations` and `timeline.items`, and exports by shelling out against the generated project. There is no write path for editorial review decisions after processing. Any "mark this clip as the best take" feature therefore has to solve four problems together:

- record the editor's override
- rebuild the active timeline from that override
- keep the desktop review UI transparent about what changed
- make export use the same active timeline the editor sees

The feature also has to preserve local-first behavior, deterministic fallback, and the analyzer's existing story-assembly heuristics instead of introducing a second timeline algorithm in the desktop frontend.

## Goals / Non-Goals

**Goals:**
- Let the editor promote a candidate segment to the active selected take for its asset from the desktop review UI.
- Let the editor clear the currently selected take for an asset so that asset is omitted from the active timeline until another take is chosen or analyzer state is restored.
- Persist that override locally for the active generated project until the user clears it or replaces the project with a new process run.
- Rebuild the active rough timeline through the existing analyzer-side story-assembly path.
- Keep analyzer scores and analyzer-selected defaults visible even after an override is applied.
- Ensure Resolve export reflects the same override-resolved timeline shown in desktop review.

**Non-Goals:**
- Adding arbitrary drag-and-drop timeline editing.
- Supporting multi-select "pin any number of beats" behavior in the first version.
- Reprocessing media or rerunning VLM analysis when the editor promotes a segment.
- Replacing analyzer scoring with manual-only editorial state.

## Decisions

### 1. Preserve analyzer output as baseline and persist overrides in a sidecar file

The app will treat `generated/project.json` as analyzer-owned baseline output and store editor overrides in a separate local sidecar file keyed to the active project identity. The sidecar will contain only the minimal override intent needed to reconstruct the active selected takes.

Rationale:
- It avoids mutating analyzer output in place and preserves a clean baseline for debugging.
- It keeps refresh and export behavior deterministic without pretending the analyzer originally emitted the override.
- It gives the desktop app a reversible override path.

Alternatives considered:
- Mutate `generated/project.json` directly: rejected because it blurs analyzer output with editor state and makes reruns/debugging brittle.
- Keep overrides in memory only: rejected because refresh/export would diverge from the visible review state.

### 2. Make the override operate at asset scope with either one active winner or no active winner in v1

Promoting a segment will make that segment the active selected take for its source asset and will clear any other selected take from that same asset in the override-resolved view. Clearing the best take will persist an explicit editor intent that leaves the asset with no active selected take. Clearing the override will restore analyzer-selected takes for that asset.

Rationale:
- It matches the current "best take" mental model and keeps the UI simple.
- It gives the editor a reversible way to drop a weak clip from the rough cut without inventing a new freeform timeline editing mode.
- It avoids mixing "replace this asset's chosen beat" with a more complex "append any beat to the timeline" model.
- It gives a deterministic contract for timeline rebuild and export.

Alternatives considered:
- Allow arbitrary extra pinned beats from the same asset: rejected because it changes the model from best-take override to full timeline editing.
- Preserve analyzer alternates alongside the manual winner: rejected for the first version because it makes override semantics ambiguous on long assets.
- Allow freeform removal without persisted override intent: rejected because refresh/export would not preserve the cleared state.

### 3. Rebuild active review state through analyzer-side helper logic, not frontend duplication

The desktop backend will call analyzer-side helper code that loads baseline project data, applies override intent, recalculates the active `take_recommendations` selection state, and rebuilds `timeline.items` with the existing story-assembly logic. The desktop frontend will render that resolved project state and separate override metadata, but it will not reimplement take selection or story assembly.

Rationale:
- It prevents logic drift between review preview and export.
- It reuses the current Python scoring and story-assembly code paths.
- It keeps the frontend focused on interaction and presentation.

Alternatives considered:
- Rebuild take selection and timeline order in TypeScript: rejected because it creates a second editorial engine.
- Export from raw overrides without rebuilding project state: rejected because review, preview, and export could diverge.

### 4. Surface override state explicitly in review and export-oriented loading

The resolved desktop project payload will include enough metadata for the UI to show whether a selected take is analyzer-chosen, editor-overridden, or editor-cleared and to offer both a clear-best-take action and a clear-override reset path. Export will consume the same resolved project state rather than the untouched baseline file.

Rationale:
- Editors need to know which choices they changed.
- It keeps the review surface auditable.
- It closes the current gap where export is wired directly to baseline generated state.

Alternatives considered:
- Hide override provenance and only show the final timeline: rejected because it makes the review state hard to trust.

## Risks / Trade-offs

- [Sidecar overrides become stale after a new process run] -> Key overrides to project identity and discard or ignore incompatible entries on reload.
- [Override-aware export drifts from review preview] -> Route both review loading and export through the same resolved-project helper path.
- [Manual promotion may reduce analyzer-selected asset diversity] -> Re-run the existing story-assembly heuristic after applying the override instead of splicing one clip into the old order.
- [Editor clears too many assets and produces an empty timeline] -> Allow the empty resolved timeline state and reflect it consistently in review and export instead of silently restoring analyzer picks.
- [Users may expect arbitrary timeline editing] -> Keep the UI language explicit that this is a best-take override, not freeform timeline editing.
- [Long-asset alternate behavior becomes less expressive in v1] -> Limit the first version to one manual winner per asset and revisit multi-beat pinning only if real use demands it.

## Migration Plan

1. Add override persistence and resolved-project loading in the desktop backend.
2. Add analyzer-side helper support for applying asset-level best-take overrides and rebuilding timeline state.
3. Add desktop review actions for promote, clear best take, and clear override, then refresh the resolved project view after each change.
4. Update export to use the resolved active project state.
5. Add tests covering baseline load, override application, timeline rebuild, and export behavior.

## Open Questions

- Should the override sidecar live next to `generated/project.json` in repo mode, or move immediately to a more app-owned path abstraction?
- Should the UI expose both "Clear best take" and "Clear override" everywhere the distinction matters, or collapse them into a single control with stronger contextual copy?
- Do we want to retain analyzer-selected alternates visually after an override, even though only one selected take per asset is active in v1?
