## 1. Frontend Module Boundaries

- [ ] 1.1 Extract shared desktop domain types, initial state factories, and frontend-only helpers out of `apps/desktop/src/main.ts`
- [ ] 1.2 Reduce `apps/desktop/src/main.ts` to a small entrypoint that boots the desktop app through dedicated bootstrap and render modules
- [ ] 1.3 Add a `platform` or equivalent frontend API module to wrap Tauri commands, event subscription, and native dialogs used by the desktop workflow

## 2. Step And Review Rendering

- [ ] 2.1 Split choose/process/settings rendering into dedicated render modules while preserving the current desktop workflow markup and behavior
- [ ] 2.2 Extract results-step view-model composition, clip grouping, and segment-card rendering into review-focused modules
- [ ] 2.3 Keep or extend `review-model`-style pure helpers so review presentation logic remains independently testable

## 3. Interaction Cleanup

- [ ] 3.1 Replace the monolithic `bindActions()` pattern with a clearer action-dispatch layer or equivalent delegated event handling
- [ ] 3.2 Preserve current interactions for media picking, process start, process log toggling, clip expansion, settings save, export, and workflow reset through the new action boundary

## 4. Verification

- [ ] 4.1 Add or extend desktop tests for extracted pure modules such as review view-models, workflow helpers, and formatting utilities
- [ ] 4.2 Run `npm exec tsc -- -p apps/desktop/tsconfig.json --noEmit` and any relevant desktop tests after the refactor
