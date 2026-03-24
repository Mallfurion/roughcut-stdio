## Context

The repository already implements an end-to-end local workflow:

- `npm run setup`
- `npm run process`
- `npm run view`
- `npm run export`

That workflow ingests media from `TIMELINE_MEDIA_DIR` or the repository `media/` folder, builds a generated project state, shows the results in a browser UI, and exports `FCPXML` for Resolve handoff. The baseline selection layer is still deterministic, while AI currently provides structured segment understanding and explanation only.

The main documentation problem is that the implemented state and the future roadmap are mixed together in `plan/`. OpenSpec should become the canonical source for what has already landed, while the remaining roadmap stays clearly future-facing.

## Goals / Non-Goals

**Goals:**

- Record the implemented baseline in OpenSpec using capability specs instead of scattered plan status notes.
- Define the current system as it actually behaves today, including its deterministic selection layer and optional AI analysis layer.
- Create a stable baseline change that future OpenSpec changes can extend, especially around AI-driven ranking, editor controls, and story assembly.

**Non-Goals:**

- Re-implement the system.
- Claim future AI-driven ranking or learning behavior that is not yet shipped.
- Replace the remaining forward-looking `plan/` materials with full OpenSpec coverage in one pass.

## Decisions

### 1. Treat this change as a baseline capture, not a new feature rollout

This change documents the shipped system rather than proposing net-new runtime behavior. That keeps the OpenSpec history grounded in the current repository state and avoids pretending that planned capabilities are already implemented.

Alternative considered:
- Rewrite all planning material directly into long-lived `openspec/specs/` without a change record.

Why rejected:
- The user asked for an OpenSpec proposal, and the implemented baseline needs a concrete change container before archival or follow-on changes can happen.

### 2. Split the baseline into capability specs by workflow boundary

The baseline is documented as five capabilities:

- `processing-workflow`
- `deterministic-screening`
- `review-workspace`
- `resolve-export`
- `ai-segment-understanding`

This mirrors the actual system boundaries in the repo and makes future changes easier to target without rewriting one oversized spec.

Alternative considered:
- One monolithic `timeline-cutter` capability.

Why rejected:
- It would make future deltas noisy and would hide the boundary between deterministic screening, UI review, export, and AI analysis.

### 3. Document current behavior, including limitations, as normative requirements

The specs explicitly describe the current constraints:

- deterministic scoring still drives take selection
- AI analysis is descriptive, not authoritative for final selection
- source-only clips remain valid when no proxy exists
- `FCPXML` is the primary export target

Alternative considered:
- Normalize the docs around the aspirational manifesto only.

Why rejected:
- That would make the specs inaccurate and reduce trust in the documentation.

### 4. Keep `plan/` as a forward-looking workspace, but point implemented baseline readers to OpenSpec

`plan/` still has value for future thinking, especially for phases that are not yet implemented. A small pointer in `plan/README.md` is enough to stop the implemented baseline from drifting in two places.

Alternative considered:
- Delete or rewrite all of `plan/` immediately.

Why rejected:
- It is unnecessary churn and would mix historical capture with roadmap rewriting.

## Risks / Trade-offs

- [Historical capture may diverge from code again] -> Mitigation: future implemented behavior should land as OpenSpec changes first, not as freeform plan edits.
- [Specs may overstate maturity] -> Mitigation: the requirements and design explicitly call out that deterministic selection remains the authoritative ranking layer today.
- [Two documentation systems remain in the repo] -> Mitigation: make OpenSpec canonical for implemented baseline and keep `plan/` focused on future work.
- [Retrospective tasks do not behave like a normal implementation checklist] -> Mitigation: mark them as completed baseline-capture tasks instead of pretending the work is pending.

## Migration Plan

1. Add the `init-deterministic-pass` OpenSpec change with proposal, design, tasks, and capability specs.
2. Point `plan/README.md` at the new OpenSpec change as the canonical baseline for implemented work.
3. Keep future changes in OpenSpec instead of adding more “implemented” status notes into `plan/`.

## Open Questions

- Should the next documentation step be to archive this change into long-lived `openspec/specs/` after reviewing the baseline?
- Should remaining future roadmap items in `plan/` be converted into separate OpenSpec changes one by one, or kept as brainstorming material until they are better scoped?
