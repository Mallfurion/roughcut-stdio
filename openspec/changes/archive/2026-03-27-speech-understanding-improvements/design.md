## Context

The current speech path already supports transcript extraction, selective probes, turn derivation, and turn-aware segmentation. That solved the first-order problem of treating speech-heavy clips like generic visual material. The remaining issue is that turns are still too shallow a unit for many real editorial cases. Interviews, voiceover sections, question-and-answer sequences, and continuous monologues can still be cut in ways that are technically turn-aligned but editorially incomplete.

The next improvement should deepen speech structure without making transcript support a hard dependency for the rest of the product.

## Goals / Non-Goals

**Goals:**
- Improve spoken-beat completeness when transcript evidence is available.
- Better preserve question/answer continuity and monologue flow.
- Keep speech-aware segmentation and scoring inspectable in generated state.
- Preserve graceful degradation when transcript support is missing or unavailable.

**Non-Goals:**
- Full diarization or speaker-identification as a requirement.
- Transcript correction or rewriting.
- Making silent footage dependent on transcript-aware logic.

## Decisions

### 1. Build on transcript turns instead of replacing them

Richer speech understanding will extend the current turn model with higher-level spoken-beat cues rather than introducing a completely separate transcript subsystem.

Rationale:
- Turn structure already exists and is part of the shipped pipeline.
- Extending it is lower risk than replacing it.

### 2. Treat spoken-beat completeness as a segmentation and scoring concern

The analyzer will use richer speech structure in both:
- segmentation or assembly decisions
- scoring decisions for speech-heavy candidates

Rationale:
- A spoken beat can be damaged either by bad boundaries or by poor ranking.
- Fixing only one side would leave the other bottleneck intact.

### 3. Keep transcript-free fallback explicit

All richer speech logic will remain conditional on usable transcript evidence. When that evidence is missing, the pipeline must continue to fall back cleanly to the current non-transcript behavior.

Rationale:
- Silent footage and transcript-free workflows remain first-class.
- Transcript support is an enhancement, not a hard dependency.

## Risks / Trade-offs

- [Speech structure heuristics may overfit interviews] -> Keep the signals general enough to cover interviews, monologues, and mixed footage rather than assuming one format.
- [Richer speech logic can increase pipeline complexity] -> Persist explicit evidence and rationale rather than hiding the logic in opaque scoring behavior.
- [Transcript quality may limit gains] -> Continue graceful fallback and avoid treating low-quality transcript hints as absolute truth.

## Migration Plan

1. Extend transcript-backed analysis with richer spoken-structure signals.
2. Integrate those signals into segmentation and scoring in bounded ways.
3. Persist the new speech-structure context in generated state and tests.
4. Verify that transcript-free runs still behave correctly.

## Open Questions

- Which spoken structures are stable enough to model now: question/answer continuity, monologue completeness, setup/payoff, or all of them?
- Is speaker-awareness necessary for the first pass, or can turn adjacency and transcript semantics carry enough of the benefit?
