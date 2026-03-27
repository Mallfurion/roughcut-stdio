## Why

The desktop app works, but [`apps/desktop/src/main.ts`](/Users/florin/Projects/personal/roughcut-stdio/apps/desktop/src/main.ts) has grown into a 1,500+ line entrypoint that mixes state, Tauri I/O, rendering, review composition, settings persistence, and DOM event wiring. That makes every desktop change riskier than it needs to be and slows down follow-on work in review, settings, and workflow features.

## What Changes

- Refactor the desktop frontend into explicit modules instead of keeping most frontend behavior in `apps/desktop/src/main.ts`.
- Preserve the current desktop workflow, Tauri command surface, and rendered behavior while separating:
  - app/domain types and default state factories
  - Tauri command and dialog access
  - workflow state transitions and bootstrap logic
  - step-level rendering for choose/process/results
  - review-card rendering and view-model composition
  - shared formatting and HTML helpers
- Replace repeated render-time DOM rebinding with a cleaner frontend action boundary so new interactions do not keep expanding a single `bindActions()` function.
- Add targeted desktop tests around extracted pure modules so review rendering and workflow state logic can evolve without relying on the full app entrypoint.

## Capabilities

### New Capabilities
- `desktop-frontend-architecture`: Defines the frontend module boundaries required to keep the desktop workflow maintainable while preserving current behavior.

### Modified Capabilities
- `desktop-workflow`: The desktop workflow implementation is reorganized behind explicit frontend modules while preserving the existing guided flow.
- `review-workspace`: The review surface implementation is reorganized so clip and segment rendering live behind dedicated review modules rather than the top-level app entrypoint.

## Impact

- Affected code:
  - `apps/desktop/src/main.ts`
  - new frontend modules under `apps/desktop/src/`
  - desktop tests for extracted pure logic
- Preserved contracts:
  - current Tauri commands in `apps/desktop/src-tauri/src/main.rs`
  - generated project payload shape
  - existing desktop step flow and Resolve export behavior
- Main benefit:
  - lower coupling for future desktop work such as review interactions, feedback capture, timeline preview, and settings expansion
