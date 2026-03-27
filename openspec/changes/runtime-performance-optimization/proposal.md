## Why

Recent process benchmarks show that repeated runs are acceptably fast once AI cache is warm, but cold runs still spend too much time on avoidable local-runtime overhead. The current analyzer does more semantic validation than the documented budget implies, rebuilds some image evidence unnecessarily, and reports MLX-local runtime cost in a way that makes configured concurrency and actual work harder to reconcile.

## What Changes

- Enforce semantic boundary validation limits as run-scoped runtime budgets instead of effectively reapplying them per asset.
- Reduce per-segment evidence generation cost by reusing prepared evidence where safe and by collapsing avoidable ffmpeg work in the keyframe/contact-sheet path.
- Make MLX-local runtime behavior match its configured execution semantics more closely, so concurrency controls and benchmark counters reflect real analyzer behavior.
- Extend benchmark and process reporting so cold-vs-warm AI work, semantic-validation request volume, and effective local-runtime activity are easier to compare.

## Capabilities

### New Capabilities

### Modified Capabilities

- `ai-segment-understanding`: runtime-budget enforcement and local-model execution requirements change so semantic validation limits and MLX-local execution behavior remain explicit, bounded, and reviewable.
- `process-benchmarking`: benchmark requirements change so cache warmth, semantic-validation request volume, and effective AI activity are preserved for run-to-run comparison.

## Impact

- `services/analyzer/app/analysis.py`
- `services/analyzer/app/ai.py`
- `services/analyzer/app/benchmarking.py`
- analyzer process summaries and benchmark artifacts under `generated/`
- runtime-focused analyzer tests and OpenSpec roadmap/documentation references
