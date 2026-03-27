## Context

Roughcut Stdio now includes multiple optional runtime layers: transcript extraction, semantic boundary validation, CLIP, local AI providers, cache reuse, and story assembly diagnostics. That richness is useful, but it also increases the chances of confusing slowdowns, partial degradation, unclear fallbacks, or hard-to-explain benchmark results.

The goal of this change is not to add more editorial intelligence. It is to make the existing intelligence easier to trust operationally.

## Goals / Non-Goals

**Goals:**
- Make expensive runtime-path activation more predictable.
- Improve visibility into fallback, cache, and degraded-mode behavior.
- Preserve richer runtime context in process and benchmark artifacts.
- Surface clearer runtime readiness or degraded-mode status in the desktop flow.

**Non-Goals:**
- Replacing current AI backends.
- Changing editorial behavior purely for quality reasons.
- Bundling standalone desktop distribution concerns into this change.

## Decisions

### 1. Treat runtime reliability as a reporting and gating problem first

The first pass will focus on:
- better runtime-state reporting
- clearer cache and fallback visibility
- tighter activation rules for expensive paths

Rationale:
- Many current reliability issues are not silent failures; they are opaque failures or hard-to-explain behavior.
- Better reporting makes later optimization decisions much easier.

### 2. Preserve degraded-mode execution instead of failing hard

Optional capabilities such as transcript support, semantic validation, or local model use will continue to degrade gracefully when unavailable or over budget. The change will improve how that degradation is surfaced rather than removing fallback behavior.

Rationale:
- Deterministic fallback is a core product constraint.
- The product must stay usable even when optional runtime layers are not healthy.

### 3. Pair runtime metrics with workload context

Benchmarks and process summaries will preserve enough workload and activation context to explain why a run changed in cost or behavior.

Rationale:
- Runtime numbers alone are not very useful if the operator cannot tell what activated or what was skipped.

## Risks / Trade-offs

- [More reporting can create noisy artifacts] -> Prefer concise structured counters and named statuses over verbose logs alone.
- [Tighter gating can hide useful AI paths] -> Keep the gating rules explicit and benchmarkable instead of silently disabling capability.
- [Desktop runtime status can become too technical] -> Surface user-facing state clearly while preserving more detailed diagnostics in generated artifacts.

## Migration Plan

1. Audit current runtime statuses, caches, and fallback paths.
2. Add clearer structured reporting for those paths in process and benchmark artifacts.
3. Tighten expensive-path activation with bounded, visible rules.
4. Expose the resulting runtime state more clearly in the desktop workflow.

## Open Questions

- Which degraded states should be user-visible in the main desktop workflow versus diagnostics-only?
- Which expensive path is the highest-value target for tighter gating first: semantic validation, transcript probing, or local model analysis?
