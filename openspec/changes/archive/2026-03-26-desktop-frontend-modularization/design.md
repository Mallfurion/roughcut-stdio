## Context

The current desktop frontend is implemented as a single vanilla TypeScript entrypoint in [`apps/desktop/src/main.ts`](/Users/florin/Projects/personal/roughcut-stdio/apps/desktop/src/main.ts). That file currently owns:

- most desktop domain types
- default settings and initial state factories
- app bootstrap and process polling
- Tauri `invoke`, event listening, and dialog usage
- step rendering for choose/process/results
- settings-dialog rendering
- results review-card rendering
- every DOM event binding through one `bindActions()` function
- small formatting and HTML helpers

That shape was acceptable to get the desktop shell shipped quickly, but it is no longer a good fit for the pace of desktop changes already underway. Review-related changes such as ranking alignment and provenance display have already increased the size and branching of the results renderer, while settings and workflow changes continue to add more action wiring.

The existing extraction of [`apps/desktop/src/review-model.ts`](/Users/florin/Projects/personal/roughcut-stdio/apps/desktop/src/review-model.ts) is a useful proof point: pure review logic becomes easier to test and reason about once it is not embedded in the app entrypoint.

## Goals / Non-Goals

**Goals:**

- Preserve the current desktop behavior and Tauri command contract.
- Reduce `main.ts` to a small bootstrap entrypoint.
- Separate state, platform integration, rendering, and review composition into distinct modules.
- Make step-level and review-level rendering reusable and testable.
- Reduce duplicated event-binding code and make future UI actions easier to add safely.

**Non-Goals:**

- Rewriting the desktop app in React, Svelte, or another framework.
- Redesigning the desktop UX, changing the three-step flow, or changing the visual system.
- Changing the Rust command API unless a tiny compatibility helper is needed.
- Solving every cross-language duplication issue in this change, such as Rust and TypeScript defaults sharing one physical source file.

## Decisions

### 1. Keep the current vanilla TypeScript rendering model

The app already renders reliably with template strings and direct DOM updates. Replacing that with a framework would multiply scope without solving the immediate problem, which is responsibility collapse inside one file.

Instead, the refactor should keep:

- `innerHTML`-based rendering
- Tauri APIs and commands
- current CSS and markup structure where practical

Alternative considered:

- Introduce a frontend framework now.
  - Rejected because it combines architecture cleanup with a stack migration and makes behavior-preservation harder to verify.

### 2. Split the frontend by responsibility, not by arbitrary file size

The new module structure should follow stable seams in the current codebase:

- `src/main.ts`
  - bootstrap only
- `src/app/types.ts`
  - shared desktop app types such as `AppState`, `AppSettings`, `TimelineProject`, and process/result payloads
- `src/app/state.ts`
  - default settings, initial state factories, and state transition helpers
- `src/app/bootstrap.ts`
  - startup flow, process listener registration, project/settings/media initialization, process polling lifecycle
- `src/platform/desktop-api.ts`
  - wrappers around `invoke`, `listen`, `open`, `save`, and `confirm`
- `src/render/app-shell.ts`
  - top-level shell and step routing
- `src/render/choose-step.ts`
  - choose-folder screen
- `src/render/process-step.ts`
  - process view
- `src/render/settings-dialog.ts`
  - settings modal rendering
- `src/render/review/clip-list.ts`
  - clip grouping and clip-card rendering
- `src/render/review/segment-card.ts`
  - segment-card rendering and related review presentation helpers
- `src/render/view-models.ts`
  - `resolveClipViews` and other project-to-view transformations
- `src/lib/format.ts` and `src/lib/html.ts`
  - formatting, provider labels, blocked-badge logic, `escapeHtml`, and similar pure helpers

This keeps each module coherent and aligned with likely future changes.

Alternative considered:

- Split only into `main.ts` plus a few utility files.
  - Rejected because it would leave state, actions, and rendering still entangled and would not materially improve maintainability.

### 3. Replace per-render rebinding with a delegated action layer

Today every render pass is followed by `bindActions()`, which re-queries and re-attaches many handlers. That makes interaction logic long, repetitive, and tightly coupled to current DOM IDs.

The refactor should move toward a small action router attached once to the app root:

- renderers emit `data-action` and contextual `data-*` attributes
- one click/change/input handler dispatches to typed action functions
- step-specific behavior stays in action modules instead of spreading across `bindActions()`

This improves DRY without changing the rendering approach.

Alternative considered:

- Keep direct rebinding and only move the function to another file.
  - Rejected because it changes file size, not architecture.

### 4. Treat results rendering as a review subsystem

The results step is already more complex than the choose/process steps. It joins assets, candidate segments, take recommendations, review provenance, and media imagery into a presentation model.

That should be modeled explicitly as:

- project view-model composition
- clip-level grouping
- segment-card rendering
- existing `review-model.ts` for recommendation/provenance summaries

This aligns with future desktop work in feedback capture and timeline preview, which will build mostly on review concerns rather than on folder selection or process polling.

Alternative considered:

- Keep results rendering inside the generic app renderer.
  - Rejected because review-specific complexity is already the dominant contributor to entrypoint growth.

### 5. Add tests only around extracted pure logic in this change

The highest-value tests for this refactor are on pure modules:

- clip-view resolution
- provider-label and blocked-badge formatting
- score and segment formatting helpers
- step-independent state helpers
- review-card view-model logic

Full DOM integration tests can follow later if needed, but the first pass should keep the refactor grounded and low-risk.

Alternative considered:

- Add broad end-to-end frontend tests as part of the same refactor.
  - Rejected because that would slow the cleanup without being required to prove the new module boundaries.

## Risks / Trade-offs

- Event delegation can become opaque if action names are inconsistent. → Mitigation: centralize action constants or use a small typed dispatcher module.
- Moving render helpers across files can accidentally change markup or CSS hooks. → Mitigation: preserve current class names and keep extraction incremental by step and by review card.
- Types may still be duplicated across Rust and TypeScript after this refactor. → Mitigation: treat frontend-only deduplication as in-scope and leave cross-language config dedup for a later, narrower change.
- Results rendering may keep growing as more review capabilities land. → Mitigation: make review rendering its own module subtree now so later changes extend the review subsystem instead of the app shell.

## Migration Plan

1. Extract shared types, state factories, and helper functions with no behavior change.
2. Extract top-level step renderers and settings dialog renderers while keeping the shell markup stable.
3. Extract results rendering into dedicated review modules, reusing the existing review-model pattern.
4. Replace `bindActions()` with delegated action handling once rendering modules are stable.
5. Add or extend tests for extracted pure modules.
6. Verify desktop TypeScript compilation and any targeted desktop tests before merging.

## Open Questions

- Should the event-delegation conversion happen in the same implementation slice as renderer extraction, or after the file split lands cleanly?
- Should the app-state helpers stay as plain object mutations, or should this change introduce a tiny store abstraction with explicit reducer-style transitions?
- Should settings defaults remain duplicated between Rust and TypeScript for now, or should that be tracked as a follow-up cleanup once the frontend split is complete?
