## Context

The current analyzer is functionally strong, but recent benchmarks show a large gap between cold and warm runs on the same dataset. The gap is not only model inference. It also reflects semantic validation activating more often than the documented budget suggests, repeated image-evidence preparation for some segments, and benchmark artifacts that do not yet explain all expensive local-runtime work clearly.

This change targets runtime cost without changing the editorial contract. It keeps the analyzer local-first, preserves deterministic fallback, and does not move any Resolve-critical behavior into model-only paths.

## Goals / Non-Goals

**Goals:**
- Reduce cold-run cost in the analyzer without weakening deterministic fallback.
- Make semantic boundary validation budgets real at run scope instead of effectively resetting them per asset.
- Cut avoidable ffmpeg and evidence-preparation work for shortlisted or semantically validated segments.
- Make MLX-local execution and benchmark counters explain actual work more faithfully.

**Non-Goals:**
- Changing story-assembly heuristics for editorial quality.
- Replacing MLX-VLM with a different provider.
- Solving missing-proxy workflows by generating proxy media inside this change.
- Expanding desktop UX beyond the diagnostics already exposed through process artifacts.

## Decisions

### 1. Apply semantic validation budgets at run scope

Semantic boundary validation selection will continue to happen against per-asset candidate segments, but the configured max-segment and percentage limits will be consumed against a run-scoped remaining budget. Once the run budget is exhausted, later eligible segments will preserve explicit `over_budget` skip metadata instead of silently behaving as though budget were refreshed for each asset.

Rationale:
- The current behavior is measurably more expensive than the documented `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS` contract suggests.
- A run-scoped budget is easier to tune, benchmark, and explain.

Alternatives considered:
- Keep the current per-asset behavior and only update docs. Rejected because the current docs and runtime expectations would stay misleading.
- Truncate semantic results after validation finishes. Rejected because it would still pay the runtime cost before discarding work.

### 2. Treat evidence preparation as a reusable asset

Prepared evidence will be reused whenever semantic validation already built evidence for a segment and the validated result did not materially change its bounds. When bounds do change, the analyzer will regenerate evidence for the new range. The keyframe/contact-sheet pipeline will also move toward fewer ffmpeg subprocesses per segment so the cold path spends less time in per-frame extraction overhead.

Rationale:
- Evidence preparation is expensive, especially on source-only runs.
- Reuse preserves the same reviewable outputs while reducing repeated work.

Alternatives considered:
- Rebuild evidence every time for simplicity. Rejected because it adds cost without improving correctness when bounds are unchanged.
- Delay all evidence generation until after final VLM targeting. Rejected because semantic validation, CLIP, and reviewable state already depend on prepared evidence earlier in the pipeline.

### 3. Separate configured AI concurrency from effective MLX execution

The analyzer will preserve configured concurrency settings, but benchmark and process reporting will distinguish configured concurrency from effective execution when a provider cannot safely honor full parallel inference. For MLX-local specifically, the design favors honest reporting and bounded execution semantics over unchecked parallel model calls. Non-model preparation work may still benefit from concurrency even if model inference remains serialized.

Rationale:
- Current benchmarks can imply that `TIMELINE_AI_CONCURRENCY` is driving MLX-local inference when the provider path remains effectively single-flight.
- Honest counters are required before deeper MLX batching work can be evaluated safely.

Alternatives considered:
- Force fully parallel MLX inference immediately. Rejected because thread-safety and model-runtime behavior are not yet established.
- Leave reporting unchanged and accept the mismatch. Rejected because it makes benchmarking less trustworthy.

### 4. Expand benchmark records around warm/cold AI work

Benchmark artifacts will record enough detail to distinguish warm-cache wins from genuine cold-path efficiency gains. This includes separating live vs cached segment-understanding work, preserving semantic-validation request volume explicitly, and surfacing effective execution context when provider behavior differs from configuration.

Rationale:
- Warm-cache runs are already much faster; the next optimization step depends on isolating what still costs time in cold runs.
- Run-to-run comparisons need to explain why a faster run happened, not just that it happened.

Alternatives considered:
- Keep only aggregate runtime deltas. Rejected because aggregate runtime alone does not explain cold-vs-warm changes or budget behavior.

## Risks / Trade-offs

- [Run-scoped semantic budgets may change which late-run segments receive validation] -> Preserve explicit skip metadata and benchmark counters so the trade-off is measurable and reviewable.
- [Fewer ffmpeg invocations can make evidence-generation code more complex] -> Keep regeneration rules narrow and cover unchanged-boundary reuse and changed-boundary rebuilds with tests.
- [Reporting effective MLX execution as lower than configured concurrency may surprise operators] -> Prefer truthful process diagnostics and benchmarks over optimistic but misleading settings echoes.
- [More benchmark counters can become noisy] -> Add only counters that explain major runtime cost changes or budget behavior.

## Migration Plan

1. Introduce run-scoped semantic-validation budget accounting and preserve over-budget skip metadata.
2. Tighten evidence reuse/regeneration rules and reduce avoidable keyframe extraction overhead.
3. Extend benchmark/process reporting with semantic-request volume and configured-vs-effective AI execution context.
4. Re-run cold and warm benchmark comparisons on the same dataset to validate that the new counters explain the runtime change.

## Open Questions

- Should MLX-local follow-up work attempt true multi-segment batching once effective execution reporting is in place?
- Do we want a separate future change for proxy-generation or stronger proxy discovery, since source-only runs still amplify decode cost even after these optimizations?
