## 1. Fixture Coverage

- [ ] 1.1 Extend the fixture manifest schema to support sequence-level expectations and broader fixture profiles.
- [ ] 1.2 Add at least one new fixture set beyond the current media-light baseline.
- [ ] 1.3 Document how fixture sets distinguish segment-level checks from sequence-level checks.

## 2. Evaluation Logic

- [ ] 2.1 Extend the evaluation pipeline to score sequence-level rough-cut behavior alongside existing segment checks.
- [ ] 2.2 Persist richer evaluation summaries that separate segment, transcript, semantic, and sequence-level results.
- [ ] 2.3 Keep the evaluation output stable enough for run-to-run comparison and release tracking.

## 3. Benchmark Integration

- [ ] 3.1 Attach the richer evaluation summary to benchmark artifacts and history entries.
- [ ] 3.2 Update process or evaluation summaries to show quality context next to runtime context.
- [ ] 3.3 Add regression tests for the expanded evaluation schema and benchmark serialization.
