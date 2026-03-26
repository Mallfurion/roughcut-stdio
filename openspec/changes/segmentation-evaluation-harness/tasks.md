## 1. Evaluation Fixtures

- [ ] 1.1 Define a stable fixture manifest covering speech-heavy, silent, montage, and mixed-content assets.
- [ ] 1.2 Add expected quality signals for each fixture set, including transcript usage and selection behavior where applicable.

## 2. Benchmark Integration

- [ ] 2.1 Extend benchmark artifacts to persist segmentation-quality counters and fixture-evaluation results.
- [ ] 2.2 Add a repeatable evaluation command or script that runs the analyzer against the fixture sets and reports quality deltas.

## 3. Validation

- [ ] 3.1 Add analyzer tests for fixture-metric collection and benchmark persistence.
- [ ] 3.2 Run `python3 -m unittest discover services/analyzer/tests -v` and the new evaluation command.

## 4. Docs

- [ ] 4.1 Update [docs/analyzer-pipeline.md](/Users/florin/Projects/personal/roughcut-stdio/docs/analyzer-pipeline.md) and [docs/commands.md](/Users/florin/Projects/personal/roughcut-stdio/docs/commands.md) to describe the evaluation workflow.
