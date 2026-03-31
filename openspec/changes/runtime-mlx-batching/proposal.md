## Why

The latest cold benchmark spent 1195 of 1201 seconds inside per-asset analysis while the configured MLX concurrency of 2 collapsed to an effective concurrency of 1. The current `mlx-vlm-local` path still analyzes shortlisted segments one request at a time, so repeated prompt, image-loading, and generation setup costs dominate large runs even when the operator has enabled concurrency.

## What Changes

- Add a batched `mlx-vlm-local` segment-understanding path so multiple shortlisted segments from the same asset can be analyzed in one local-model invocation when the runtime supports it.
- Preserve the existing deterministic fallback and serialized single-segment path when batching is unavailable, rejected by the runtime, or fails during execution.
- Keep persisted evidence bundles, review state, and segment-understanding records stable so batched execution changes runtime cost without hiding how each segment was evaluated.
- Extend process diagnostics and benchmark artifacts so they distinguish serialized-local execution from batched-local execution, including configured request volume versus effective batch behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-segment-understanding`: `mlx-vlm-local` execution may satisfy multiple shortlisted segment-understanding requests through one batched local-model invocation while preserving deterministic fallback and per-segment reviewability.
- `process-benchmarking`: benchmark and process-summary artifacts will distinguish batched-local execution from serialized-local execution so runtime gains are attributable instead of inferred.

## Impact

- `services/analyzer/app/ai.py`
- `services/analyzer/app/ai_runtime/prompts.py`
- `services/analyzer/app/ai_runtime/normalize.py`
- `services/analyzer/app/analysis.py`
- `services/analyzer/app/benchmarking.py`
- `services/analyzer/tests/test_ai.py`
- `services/analyzer/tests/test_analysis.py`
- `services/analyzer/tests/test_benchmarking.py`
- `docs/analyzer-pipeline.md`
- `docs/configuration.md`
