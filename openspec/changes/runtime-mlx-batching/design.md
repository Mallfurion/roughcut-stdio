## Context

The current analyzer already batches segment-understanding requests for `lmstudio`, but the `mlx-vlm-local` path still evaluates shortlisted segments one at a time. In the latest cold benchmark, per-asset analysis consumed almost the entire run and the configured AI concurrency of 2 was reported as an effective concurrency of 1 because the local MLX runtime serialized model access.

This change is performance-motivated, but it touches multiple analyzer layers:

- `analysis.py` builds per-asset AI task lists and records run summaries.
- `ai.py` owns the MLX runtime object, provider adapters, batch coordination hooks, and runtime stats.
- `ai_runtime/prompts.py` and `ai_runtime/normalize.py` already contain batch-oriented helpers used by LM Studio.
- benchmark and process-summary artifacts must remain able to explain configured versus effective execution behavior honestly.

The design must preserve the local-first workflow, deterministic fallback, silent-footage support, and existing reviewability of persisted segment state. Editors still need one understanding record per segment even if the runtime executes those requests in batches internally.

## Goals / Non-Goals

**Goals:**
- Reduce `mlx-vlm-local` wall-clock time by replacing per-segment invocation with per-asset batch execution where the local runtime can support it.
- Preserve deterministic fallback at the segment level so one malformed or missing batch item does not force the whole asset into failure.
- Reuse existing batch prompt and normalization helpers where possible instead of creating a second incompatible batching contract.
- Keep process logs and benchmark artifacts explicit about whether MLX executed in serialized or batched mode and how many live requests were actually issued.

**Non-Goals:**
- Implementing cross-asset deduplication changes in this proposal.
- Reworking the full per-asset pipeline into a multi-stage concurrent scheduler.
- Replacing MLX with another local model backend.
- Changing take selection, review semantics, or export behavior.

## Decisions

### 1. Add an explicit MLX batch-analysis path rather than relying on thread concurrency

`mlx-vlm-local` should gain an explicit batch entry point for segment understanding instead of trying to make the existing single-image `query_image()` path concurrent with threads.

Rationale:
- The current runtime is intentionally serialized behind a lock, so increasing thread count does not improve throughput.
- The benchmarked workload usually contains 2-4 VLM targets per asset, which is large enough to benefit from per-asset batching even without cross-asset scheduling.
- A first-class batch API makes the execution mode inspectable and testable rather than implicitly hoping the model library parallelizes safely.

Implementation direction:
- Extend the local runtime protocol with a multi-image or multi-segment batch method.
- Keep `query_image()` as the fallback path for runtimes or edge cases that cannot batch.
- Update `MLXVLMVisionLanguageAnalyzer.analyze_asset_segments()` to mirror the LM Studio flow: collect cached hits, submit one live batch for pending items, normalize results per segment, and only fall back per missing or failed segment.

Alternatives considered:
- Remove the runtime lock and rely on `TIMELINE_AI_CONCURRENCY`: rejected because the current MLX runtime path is not structured to prove thread-safe parallel generation, and the benchmark already shows that configured concurrency does not map to actual throughput.
- Spawn multiple MLX model processes: rejected for this change because it increases memory pressure and operational complexity before testing whether prompt-level batching is sufficient.

### 2. Use one batch prompt contract for MLX and LM Studio, with provider-specific normalization risk flags

MLX batching should reuse the existing batch-output shape centered on a top-level `segments` array and `segment_id` keys. Provider-specific fallback labels may differ, but the payload contract should stay shared.

Rationale:
- The repository already has batch prompt builders and batch normalization helpers for LM Studio.
- A shared payload shape keeps persisted `SegmentUnderstanding` records identical regardless of which provider produced them.
- Shared normalization makes it easier to compare MLX and LM Studio behavior in tests and process diagnostics.

Implementation direction:
- Add an MLX-specific batch prompt variant only if the local model needs more constrained wording than the current generic batch prompt.
- Reuse `normalize_batch_model_output()` as the base path, but ensure provider-specific risk flags and rationale text identify incomplete MLX batch results clearly.
- Maintain per-segment cache keys so cached and live results can mix inside the same asset batch without changing persisted review state.

Alternatives considered:
- Define a separate MLX-only batch response schema: rejected because it adds another normalization path without user-facing benefit.
- Cache whole-asset batch responses only: rejected because the existing cache is segment-scoped and segment-level reuse is more resilient when one segment changes.

### 3. Expose batched-local execution explicitly in runtime stats and benchmarks

The runtime summary and benchmark artifacts should distinguish serialized-local execution from batched-local execution instead of only reporting configured concurrency and total live segment counts.

Rationale:
- The current diagnostics already distinguish configured concurrency from effective execution context for MLX.
- Once batching exists, elapsed time deltas will be hard to interpret unless the artifacts also show whether the run used serialized or batched local-model requests.
- Honest reporting is part of the product contract for local-first runtime controls.

Implementation direction:
- Keep `ai_live_segment_count` as the segment-level unit.
- Preserve `ai_live_request_count` as the provider-call unit, so batching naturally lowers that number.
- Add batch-context reporting such as `batched-local-model` execution context and, if useful, an explicit batch request counter or batch size summary.
- Update process summaries so operators can see that MLX executed fewer live requests than live analyzed segments.

Alternatives considered:
- Only rely on elapsed time improvements and leave the counters unchanged: rejected because the benchmark system is explicitly intended to explain why runtime changed.

## Risks / Trade-offs

- [MLX batch prompting produces less reliable JSON than single-segment prompts] -> Keep per-segment fallback behavior and normalize incomplete batch results back to deterministic understanding for only the affected segments.
- [Batching increases peak memory use by loading more image evidence at once] -> Scope batching per asset, cap batch size to the existing shortlisted task list, and retain a serialized fallback path when the runtime cannot support a larger batch safely.
- [Provider behavior becomes harder to compare across LM Studio and MLX] -> Keep one shared response contract and one segment-level persisted understanding shape across providers.
- [Benchmark counters become noisy if request and segment units are mixed] -> Preserve both segment-level and request-level counters, and document the distinction in process reporting.
- [A batch failure could hide individual successful segments] -> Normalize on a per-segment basis and fall back only for missing or invalid batch items instead of discarding the entire asset result.

## Migration Plan

1. Add the batch-capable MLX runtime and analyzer adapter path behind the existing provider selection flow.
2. Update batch prompts, normalization, runtime stats, and benchmark/reporting fields together so the new execution mode is visible immediately.
3. Verify cached-only, mixed cached/live, and fully live MLX asset batches in tests before enabling the path by default.
4. Keep the serialized single-segment MLX path available as the rollback path if batch behavior is unstable on real footage.

Rollback strategy:
- Revert `MLXVLMVisionLanguageAnalyzer.analyze_asset_segments()` to the current per-segment loop and keep the single-image runtime query path as the stable fallback.

## Open Questions

- Does the current MLX-VLM stack accept one multi-image prompt cleanly enough for per-asset batching, or will it need a small fixed batch size and multiple sub-batches per asset?
- Should boundary-validation requests also reuse the new batch path later, or should this change remain limited to segment-understanding requests only?
- Do we want a new benchmark field for average MLX batch size, or is `ai_live_request_count` versus `ai_live_segment_count` sufficient?
