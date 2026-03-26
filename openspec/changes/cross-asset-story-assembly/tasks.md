## 1. Sequence Modeling

- [ ] 1.1 Add project-level sequence-scoring inputs that relate selected units across assets.
- [ ] 1.2 Define bounded heuristics for continuity, diversity, pacing, and role fit.

## 2. Timeline Assembly

- [ ] 2.1 Update timeline assembly to use sequence-level scoring instead of only independent winner ordering.
- [ ] 2.2 Persist story-assembly rationale and sequence-group metadata in generated project state.

## 3. Review

- [ ] 3.1 Surface sequence-level rationale and grouping in the desktop review workspace.

## 4. Validation

- [ ] 4.1 Add analyzer tests for ordering, grouping, and timeline-summary behavior under project-level assembly.
- [ ] 4.2 Run `python3 -m unittest discover services/analyzer/tests -v` and project-level evaluation scenarios.

## 5. Docs

- [ ] 5.1 Update [docs/analyzer-pipeline.md](/Users/florin/Projects/personal/roughcut-stdio/docs/analyzer-pipeline.md), [docs/architecture.md](/Users/florin/Projects/personal/roughcut-stdio/docs/architecture.md), and [docs/ROADMAP.md](/Users/florin/Projects/personal/roughcut-stdio/docs/ROADMAP.md).
