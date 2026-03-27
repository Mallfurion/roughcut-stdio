## Why

The current evaluation harness is useful, but it still measures mostly segment-level quality on a narrow fixture set. As story assembly and analyzer behavior get more sophisticated, the product needs broader, more repeatable evaluation that can catch sequence-level regressions and make tuning decisions defensible.

## What Changes

- Expand the fixture-driven evaluation workflow beyond the current media-light baseline.
- Add sequence-level and rough-cut quality checks alongside existing segment-level checks.
- Preserve richer evaluation summaries in benchmark artifacts so runs can be compared over time and across releases.
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
