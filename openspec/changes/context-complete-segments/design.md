## Context

The current pipeline can find promising footage, but it still confuses “interesting moment” with “usable edit unit.” The two recent proposals isolate different symptoms of the same product problem:

- `dynamic-segment-windows` tries to make raw windows less arbitrary
- `vlm-boundary-refinement` tries to recover completeness after initial analysis

Both are directionally useful, but the real system needs one segmentation pipeline that starts with cheap evidence, refines boundaries deterministically wherever possible, and uses AI only where deterministic structure is insufficient. That pipeline must remain local-first, keep deterministic fallback intact, and preserve reliable Resolve handoff. This document is now the architectural umbrella for the split child changes rather than an implementation-ready design on its own.

## Goals / Non-Goals

**Goals:**
- Produce candidate segments that correspond to context-complete narrative beats rather than raw peak windows
- Resolve as much boundary quality as possible with deterministic structure before invoking extra AI
- Use semantic refinement selectively for ambiguous segments, with explicit runtime cost controls
- Preserve provenance so editors can inspect how a final segment was formed
- Keep downstream scoring, recommendation, and export behavior compatible with the existing local-first workflow
- Provide a shared architectural reference for the split child changes

**Non-Goals:**
- Full story assembly across unrelated assets
- Speaker diarization or transcript correction as part of this change
- Frame-accurate editorial trimming
- Replacing deterministic segmentation with an always-on VLM pipeline

## Decisions

### 1. Treat low-cost windows as seed regions, not final segments

The analyzer will generate a denser set of seed regions from scene boundaries, visual peaks, audio peaks, and transcript turn hints. Those seed regions are intermediate structures that feed refinement; they are no longer assumed to be the units that reach scoring and timeline assembly.

Rationale:
- The current system overcommits too early to windows that were only meant to be cheap proxies for interesting regions.
- Reframing them as seeds makes both deterministic and semantic refinement composable.

Alternatives considered:
- Keep one final window per peak and just tune the sizing heuristic: rejected because it does not solve fragmented dialogue or merged multi-idea windows.
- Move directly to transcript-driven segmentation only: rejected because silent footage must remain first-class.

### 2. Deterministic boundary refinement runs before any semantic escalation

Each seed region will be snapped, extended, or trimmed using local structure in this order of preference:

1. transcript utterance coverage or text-span boundaries when available
2. silence gaps and audio-energy transitions
3. scene boundaries
4. seed-local duration heuristics

The refinement stage produces a boundary strategy and confidence score. High-confidence results proceed without extra AI.

Rationale:
- Most boundary problems are structural, not semantic.
- Deterministic first keeps runtime predictable and preserves the fallback guarantee.

Alternatives considered:
- VLM validation on every shortlisted segment: rejected because cost and latency scale poorly and failure modes become harder to reason about.
- Scene-only snapping: rejected because it fails on dialogue within a single scene and on silent visual actions that do not map cleanly to cuts.

### 3. Semantic boundary validation is selective, bounded, and fallback-safe

Only ambiguous refined segments will be sent through a boundary-validation pass. Ambiguity is triggered when deterministic refinement cannot confidently decide whether the segment is complete, whether it needs extension, or whether it contains multiple ideas. This pass uses the segment evidence plus short neighboring context summaries and transcript snippets when available.

The runtime will cap semantic boundary validation by percentage or count, and when AI is unavailable the pipeline will continue with deterministic results unchanged.

Rationale:
- Semantic judgment is most valuable at the boundary cases, not as a blanket replacement for deterministic structure.
- The product must remain usable without AI or when AI is partially unavailable.

Alternatives considered:
- Merge semantic validation into the initial understanding prompt: rejected because it couples segment comprehension and boundary diagnosis too tightly and makes debugging harder.
- Re-run full multimodal analysis after every boundary change: rejected for cost and complexity.

### 4. Narrative-unit assembly happens after boundary refinement and before final scoring

Refined regions will be assembled into final candidate segments through merge/split rules:

- merge adjacent refined regions when continuity evidence suggests one narrative beat
- split refined regions when transcript turns or semantic validation show multiple ideas

This stage outputs the units that reach final scoring, recommendation, and timeline assembly.

Rationale:
- Completeness is not only about start/end points; sometimes the right answer is one larger unit, and sometimes it is two smaller ones.
- Ranking should operate on the units the editor will actually inspect.

Alternatives considered:
- Merge only after scoring: rejected because scoring fragmented regions biases selection before continuity is resolved.
- Never split, only merge: rejected because long mixed-purpose segments remain hard to understand and rank.

### 5. Persist provenance as first-class review data

Final candidate segments will carry provenance describing:

- source seed region IDs or source intervals
- boundary strategy used (`transcript-snap`, `audio-snap`, `scene-snap`, `semantic-extend`, `semantic-split`, etc.)
- whether semantic refinement ran
- merge/split reasons
- boundary confidence

The review workspace will expose this metadata so editors can audit the proposal rather than trust opaque behavior.

Rationale:
- Editorial trust depends on inspectability.
- Provenance also supports debugging and future feedback-learning work.

Alternatives considered:
- Keep provenance only in logs: rejected because it is not editor-visible and is hard to validate after the fact.

## Risks / Trade-offs

- [Higher implementation complexity] -> Keep the rollout staged behind flags and make each phase independently testable.
- [Transcript timing quality varies across assets] -> Prefer transcript-aware snapping only when timing metadata is available and internally consistent; otherwise fall back to audio and scene structure.
- [Semantic refinement can increase runtime] -> Cap semantic validation volume, cache decisions, and run it only on ambiguous regions.
- [Merge/split logic may overcorrect] -> Persist provenance, expose it in review, and keep deterministic thresholds configurable.
- [Schema growth in generated project state] -> Add only bounded, review-relevant provenance fields and preserve existing fields for compatibility.

## Migration Plan

1. Implement `deterministic-boundary-refinement`.
2. Implement `narrative-unit-assembly` on top of deterministic refinement.
3. Implement `semantic-boundary-validation` for ambiguous cases only.
4. Implement `segment-provenance-review` once the underlying behavior is stable enough to inspect.
5. Promote the refined-unit path to default once parity and review visibility are verified.

## Open Questions

- What transcript timing granularity is available in the current transcript provider: segment excerpts only, or word/utterance spans?
- Should semantic boundary validation run before or after initial understanding for ambiguous speech-heavy segments?
- Do we want one unified confidence score for refinement, or separate confidence fields per boundary strategy?
