## 1. Feedback Capture

- [ ] 1.1 Define local feedback-event structures for accept, reject, trim, reorder, and alternate-choice actions.
- [ ] 1.2 Capture those events from desktop review and timeline workflows.

## 2. Persistence

- [ ] 2.1 Persist feedback events in local project or adjacent artifact storage.
- [ ] 2.2 Expose feedback summaries in a reviewable or inspectable form.

## 3. Heuristic Adaptation

- [ ] 3.1 Add bounded heuristic readers that use repeated feedback patterns to influence later analyzer decisions.
- [ ] 3.2 Preserve editor visibility and override control when learned adjustments are applied.

## 4. Validation

- [ ] 4.1 Add desktop and analyzer tests for feedback capture, persistence, and heuristic application.
- [ ] 4.2 Run `python3 -m unittest discover services/analyzer/tests -v` and `npm exec tsc -- -p apps/desktop/tsconfig.json --noEmit`.

## 5. Docs

- [ ] 5.1 Update [docs/architecture.md](/Users/florin/Projects/personal/roughcut-stdio/docs/architecture.md), [docs/ROADMAP.md](/Users/florin/Projects/personal/roughcut-stdio/docs/ROADMAP.md), and review-related documentation.
