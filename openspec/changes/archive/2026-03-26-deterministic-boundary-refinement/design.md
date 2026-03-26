## Context

The current pipeline uses scene windows and peak windows as if they were already usable edit units. That creates brittle downstream behavior: ranking, AI understanding, and timeline assembly all inherit bad boundaries. This change introduces the first half of the new segmentation model: deterministic refinement of cheap seed regions into better-bounded candidate segments.

## Goals / Non-Goals

**Goals:**
- Introduce seed regions as an intermediate structure
- Deterministically refine boundaries before scoring and AI understanding
- Reuse local structure already available in the analyzer
- Preserve deterministic fallback and local-first behavior

**Non-Goals:**
- Narrative merging or splitting
- VLM-based boundary decisions
- Full provenance UI in the desktop app

## Decisions

### 1. Seed regions become an explicit intermediate structure

The prefilter stage will output seed regions with source labels such as `scene`, `visual-peak`, `audio-peak`, or `fallback`. Downstream refinement consumes those seeds to produce final candidate segments.

Rationale:
- It separates “interesting area detection” from “usable segment construction.”
- It makes later merge/split and semantic refinement stages possible without rewriting prefilter logic again.

### 2. Deterministic refinement prefers transcript, then audio, then scene structure

Boundary refinement will use this precedence:

1. transcript-span snapping when timed transcript spans are available
2. audio silence gaps and energy transitions
3. scene boundaries
4. bounded duration heuristics

Rationale:
- Speech-heavy clips benefit most from transcript and silence structure.
- Silent or transcript-light clips still need scene-based and heuristic fallback.

### 3. Transcript access is upgraded to timed spans

The transcript layer currently exposes excerpt text only. This change adds an internal way to retrieve timed spans for a time range so transcript-aware snapping can be implemented without changing the user workflow.

Rationale:
- Deterministic transcript-aware snapping is not viable if the analyzer can only ask for plain text excerpts.
- The whisper adapter already caches timed spans internally, so the data exists.

### 4. Every refined segment carries a strategy label and confidence score

Refinement output will include:
- `boundary_strategy`
- `boundary_confidence`
- source seed identifiers or intervals

Rationale:
- Later stages need to know which segments are robust and which are ambiguous.
- This also prepares the path for semantic validation without coupling the two changes.

## Risks / Trade-offs

- [Transcript timing may be absent or noisy] -> Only use transcript snapping when timed spans are present and consistent.
- [Too many refinement rules can become opaque] -> Keep strategy labels explicit and write tests per rule family.
- [Legacy parity may regress] -> Roll out behind a feature flag and compare output against the existing path.
