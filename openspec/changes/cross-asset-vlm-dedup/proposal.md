## Why

The current runtime still sends many repetitive segments to VLM analysis because semantic deduplication happens inside the per-asset loop instead of across the full shortlisted pool. On repetitive multi-camera or repeated-drone footage, that means the analyzer pays model cost for near-identical shots that should have been collapsed before VLM targeting.

## What Changes

- Move shortlist deduplication to a global cross-asset pass that runs after evidence building and CLIP scoring but before final VLM target selection.
- Keep CLIP-based semantic dedup as the preferred path and preserve histogram-based fallback when CLIP is unavailable, disabled, or fails to load.
- Preserve review-state visibility for eliminated segments, including keeper identity, cross-asset dedup group membership, and the reason a duplicate did not reach VLM.
- Extend process diagnostics and benchmarks so the runtime impact of global dedup is visible in eliminated-count and VLM-target-count changes rather than hidden inside total runtime.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `clip-deduplication-semantic`: the semantic dedup pass will execute on the combined shortlisted pool across assets before VLM targeting, so keeper selection and duplicate elimination can reduce cross-asset model work directly.
- `ai-segment-understanding`: segments removed by global cross-asset dedup will remain reviewable as deterministic-only outcomes with explicit skip reasons instead of silently disappearing from the AI path.

## Impact

- `services/analyzer/app/analysis.py`
- `services/analyzer/app/clip_dedup.py`
- `services/analyzer/app/deduplication.py`
- `services/analyzer/app/benchmarking.py`
- `services/analyzer/tests/test_analysis.py`
- `services/analyzer/tests/test_deduplication.py`
- `services/analyzer/tests/test_benchmarking.py`
- `docs/analyzer-pipeline.md`
- `docs/pipeline-improvements.md`
