## Why

The analyzer now has enough layered logic that qualitative inspection alone is no longer enough to judge whether a change is actually better. Transcript targeting, deterministic refinement, assembly rules, and semantic validation all need a repeatable evaluation surface.

## What Changes

- Add a segmentation evaluation harness for representative fixture sets.
- Define persisted quality metrics that let process runs compare boundary quality, transcript use, and semantic-validation activation over time.
- Make segmentation changes measurable before deeper turn-structure and semantic-calibration work.

## Capabilities

### New Capabilities
- `segment-quality-evaluation`: Evaluate segmentation quality against fixed fixtures and persist comparable metrics.

### Modified Capabilities
- `process-benchmarking`: Benchmark artifacts must include segmentation-quality workload and result metrics where available.

## Impact

- Analyzer benchmarking and validation utilities
- Generated benchmark artifacts under `generated/benchmarks/`
- Test fixtures and repeatable process verification flow
