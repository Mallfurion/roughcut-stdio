## 1. Fixture Coverage

- [x] 1.1 Extend the fixture manifest schema to support sequence-level expectations and broader fixture profiles.
- [x] 1.2 Add at least one new fixture set beyond the current media-light baseline.
- [x] 1.3 Document how fixture sets distinguish segment-level checks from sequence-level checks.

## 2. Evaluation Logic

- [x] 2.1 Extend the evaluation pipeline to score sequence-level rough-cut behavior alongside existing segment checks.
- [x] 2.2 Persist richer evaluation summaries that separate segment, transcript, semantic, and sequence-level results.
- [x] 2.3 Keep benchmark comparisons scoped to repeated runs of the same dataset while leaving portable fixture validation as the pass/fail contract.

## 3. Benchmark Integration

- [x] 3.1 Attach the richer evaluation summary to benchmark artifacts and history entries.
- [x] 3.2 Update process or evaluation summaries to show quality context next to runtime context.
- [x] 3.3 Add regression tests for the expanded evaluation schema and benchmark serialization.
