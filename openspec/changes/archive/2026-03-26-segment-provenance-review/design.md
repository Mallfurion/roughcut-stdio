## Context

The segmentation pipeline is becoming more intelligent and more layered. That is good for output quality, but it also means the editor can no longer infer segment construction from start/end times alone. This change makes refinement behavior reviewable without bloating the interface or touching export correctness.

## Goals / Non-Goals

**Goals:**
- Persist bounded provenance that explains final segment formation
- Show provenance in the desktop review workspace
- Keep Resolve handoff untouched
- Make ambiguity and refinement outcomes inspectable

**Non-Goals:**
- Rebuilding the review UI
- Exposing every internal heuristic to the editor
- Changing scoring or export logic

## Decisions

### 1. Provenance is stored once in project state and rendered in the UI

The analyzer will persist normalized provenance fields, and the desktop app will render a concise view of those fields instead of reconstructing explanations client-side.

Rationale:
- Keeps business logic in the analyzer.
- Makes tests and future integrations easier.

### 2. The UI shows summary provenance, not raw internals

The review surface will show concise labels such as boundary strategy, confidence, semantic-validation status, and merge/split lineage summaries.

Rationale:
- Editors need trust signals, not implementation dumps.

### 3. Export remains unchanged

Provenance is informational only. It must not alter source references, trim safety, or Resolve export semantics.

Rationale:
- Review explainability and interchange correctness are separate concerns.

## Risks / Trade-offs

- [Too much provenance can clutter review] -> Limit the UI to the highest-signal fields and keep the rest in project state.
- [Schema growth can get messy] -> Normalize provenance fields and reuse them across review surfaces.
- [UI may drift from analyzer behavior] -> Render persisted fields directly rather than recreating logic client-side.
