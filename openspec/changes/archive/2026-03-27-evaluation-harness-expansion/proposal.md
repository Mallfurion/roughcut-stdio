## Why

The current evaluation harness is useful, but it still needs a cleaner split between portable correctness checks and real-dataset benchmarking. As story assembly and analyzer behavior get more sophisticated, the project needs shared repo-owned fixtures for pass/fail validation and dataset-aware benchmark comparisons for repeated runs on the same footage.

## What Changes

- Replace private-footage assumptions in the shared evaluation baseline with portable repo-owned fixtures.
- Add sequence-level and rough-cut quality checks alongside existing segment-level checks.
- Preserve richer evaluation summaries in benchmark artifacts so repeated runs on the same dataset can be compared without treating different datasets as regressions.
- Keep portable fixture validation and real-dataset benchmarking as separate modes rather than one blended pass/fail system.
- Keep evaluation aligned with the current local-first analyzer flow rather than creating a separate research-only harness.

## Capabilities

### New Capabilities

### Modified Capabilities
- `segment-quality-evaluation`: Evaluation requirements expand from segmentation-focused checks to broader sequence-quality and fixture-coverage expectations.
- `process-benchmarking`: Benchmark artifacts must preserve evaluation context and comparison-friendly quality summaries beyond raw runtime metrics.

## Impact

- `services/analyzer/app/segmentation_evaluation.py`
- `services/analyzer/app/benchmarking.py`
- `services/analyzer/scripts/evaluate_segmentation.py`
- `fixtures/segmentation-evaluation.json`
- generated evaluation summaries and benchmark artifacts
