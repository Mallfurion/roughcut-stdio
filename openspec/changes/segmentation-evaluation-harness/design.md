## Context

The current analyzer can now:

- refine and assemble candidate segments
- target transcripts selectively
- run bounded semantic validation

But the project has no stable answer for questions like:

- did this change reduce truncated speech beats?
- did transcript probing skip useful transcript-backed segments?
- did semantic validation activate on the right segments?

## Goals / Non-Goals

**Goals:**
- define a repeatable evaluation workflow for segmentation quality
- cover speech-heavy, silent, montage, and mixed-content fixtures
- persist quality metrics beside timing benchmarks

**Non-Goals:**
- automatic model training
- cloud benchmarking infrastructure
- replacing unit tests

## Decisions

### 1. Use fixed local fixture sets

The harness will use a small curated fixture set committed to the repo or referenced locally in a stable way.

Why:
- analyzer regressions need deterministic reproduction

### 2. Focus on quality metrics, not just runtime

Metrics should include at least:

- candidate count and selected count
- transcript-targeted / skipped / probed / rejected counts
- transcript excerpt segment count
- speech fallback segment count
- semantic boundary eligible / validated counts
- manually reviewed segmentation expectations for selected fixtures

### 3. Keep the harness process-adjacent

The harness should build on `npm run process` and current benchmark artifact formats instead of inventing a disconnected evaluation subsystem.

## Risks / Trade-offs

- hand-curated fixtures require maintenance
- editorial-quality expectations will start coarse before they mature

## Migration Plan

1. Add fixture manifests and expected metrics.
2. Persist quality metrics in benchmark records.
3. Add a verification command or script for repeatable evaluation runs.
4. Use the harness as the baseline for later transcript-turn and semantic-validation work.
