## Why

The analyzer now has more capable transcript, semantic, and story-assembly paths, but that also makes the runtime harder to reason about. The next step is to make the pipeline more predictable, more observable, and more resilient when optional features are slow, unavailable, or partially degraded.

## What Changes

- Improve runtime observability for transcript, semantic, cache, and fallback behavior.
- Tighten runtime gating so expensive paths activate more predictably and safely.
- Preserve clearer failure and fallback reporting in generated artifacts and desktop-visible status.
- Strengthen benchmark and process reporting so performance tuning can be done with better context.

## Capabilities

### New Capabilities

### Modified Capabilities
- `processing-workflow`: Process requirements expand to include clearer fallback, cache, and degraded-runtime reporting.
- `process-benchmarking`: Benchmark requirements expand to preserve richer runtime-stability and gating context.
- `ai-segment-understanding`: AI runtime behavior and fallback requirements expand to make activation, skipping, and degradation more explicit.
- `desktop-workflow`: Desktop workflow requirements expand to surface clearer runtime readiness and degraded-mode status to the user.

## Impact

- `services/analyzer/app/benchmarking.py`
- `services/analyzer/app/analysis.py`
- `services/analyzer/app/ai.py`
- desktop runtime checks and process status surfaces
- generated process summaries, benchmark artifacts, and runtime diagnostics
