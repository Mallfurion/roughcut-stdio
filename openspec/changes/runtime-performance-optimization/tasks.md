## 1. Semantic Validation Budgeting

- [ ] 1.1 Refactor semantic boundary validation targeting so configured validation budgets are enforced across the full process run instead of effectively resetting per asset.
- [ ] 1.2 Preserve explicit over-budget skip metadata and summary counters for eligible segments that are not validated because the run budget is exhausted.
- [ ] 1.3 Add analyzer tests that prove run-scoped semantic budgets cap validation volume across multiple assets.

## 2. Evidence Pipeline Efficiency

- [ ] 2.1 Reduce avoidable evidence-generation work by reusing prepared evidence when semantic validation leaves segment bounds unchanged and regenerating only when bounds materially change.
- [ ] 2.2 Collapse per-segment keyframe/contact-sheet preparation into fewer ffmpeg subprocesses while preserving reviewable image outputs and deterministic fallback behavior.
- [ ] 2.3 Add regression tests for unchanged-boundary evidence reuse, changed-boundary evidence regeneration, and contact-sheet generation behavior.

## 3. MLX Runtime And Benchmark Reporting

- [ ] 3.1 Align MLX-local runtime reporting with actual execution semantics so configured concurrency and effective execution context are both preserved when they differ.
- [ ] 3.2 Extend benchmark artifacts and process summaries with semantic-validation request counts, warm-vs-cold AI activity counters, and any configured-vs-effective AI execution context required by the updated specs.
- [ ] 3.3 Tighten process-summary and end-of-run analysis bookkeeping so the expanded runtime fields do not rely on repeated runtime-status resolution or avoidable late-stage segment lookup scans.
- [ ] 3.4 Add benchmark serialization and comparison tests covering cache-warm runs, semantic-validation request volume, and effective execution reporting.

## 4. Documentation And Validation

- [ ] 4.1 Update runtime-related docs and examples for semantic validation budgeting, benchmark interpretation, any changed AI runtime reporting fields, and the chained follow-up boundary where relevant.
- [ ] 4.2 Run targeted validation with `python3 -m unittest discover services/analyzer/tests -v` or focused analyzer test subsets plus at least one cold/warm benchmark comparison on the same dataset.
