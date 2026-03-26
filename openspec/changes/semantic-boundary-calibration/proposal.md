## Why

Semantic boundary validation is implemented, but current runs show that it often stays dormant because the ambiguity gate and targeting rules are too conservative. After transcript-turn structure exists, the next step is to calibrate semantic validation so it activates where it materially improves output.

## What Changes

- Retune semantic-boundary eligibility and ambiguity scoring using transcript-turn-aware evidence and evaluation-harness results.
- Add bounded activation rules so borderline runs do not end with zero semantic validation targets by default.
- Persist benchmark-facing metrics that explain when semantic validation helped, skipped, or stayed dormant.

## Capabilities

### Modified Capabilities
- `context-complete-segmentation`: Ambiguity scoring and semantic-validation targeting must be calibrated against real segment structures.
- `ai-segment-understanding`: Persist richer semantic-validation activation, skip, and impact metadata.
- `process-benchmarking`: Benchmark artifacts must record semantic-validation activation and impact metrics.

## Impact

- Analyzer ambiguity scoring and selection logic
- Benchmarking and evaluation output
- Generated segment provenance and validation metadata
