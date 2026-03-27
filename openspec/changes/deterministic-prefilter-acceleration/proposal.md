## Why

This change is a chained follow-up to `runtime-performance-optimization`. Once later-stage evidence reuse, semantic-validation budgeting, and truthful AI runtime reporting are in place, the biggest remaining cold-path cost is still the deterministic front half of the analyzer: prefilter frame sampling spawns too many `ffmpeg` processes, audio screening scans the same asset more than once, and repeat runs rebuild the same screening artifacts even when the source media and settings did not change.

## What Changes

- Batch deterministic frame extraction for prefilter sampling so the analyzer no longer pays one `ffmpeg` process per sampled timestamp.
- Consolidate deterministic audio screening into a single bounded asset pass that can feed silence detection, RMS energy, transcript targeting, transcript probing, and audio-seed generation from shared extracted measurements.
- Persist reusable deterministic preprocessing artifacts for compatible runs, starting with scene boundaries, sampled frame signals, and sampled audio signals.
- Rebuild deterministic preprocessing artifacts when the source media or relevant screening configuration changes, without weakening source-only fallback or transcript-free workflows.
- Extend benchmark and process reporting so cold-vs-warm deterministic preprocessing work and asset-level screening reuse are visible separately from AI cache effects.

## Capabilities

### New Capabilities

### Modified Capabilities

- `deterministic-screening`: preprocessing requirements change so screening may batch frame/audio extraction work and reuse persisted deterministic preprocessing artifacts across compatible runs while preserving candidate-generation behavior.
- `process-benchmarking`: benchmark requirements change so deterministic preprocessing cache warmth, asset-level reuse, and front-half screening activity are preserved for comparison.

## Impact

- `services/analyzer/app/prefilter.py`
- `services/analyzer/app/analysis.py`
- deterministic preprocessing artifacts under `generated/analysis/`
- process summaries and benchmark artifacts under `generated/benchmarks/`
- analyzer tests covering prefilter sampling, preprocessing cache invalidation, and benchmark reporting
