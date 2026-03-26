## Context

The current transcript path provides:

- timed transcript spans
- transcript excerpts for candidate ranges
- selective transcript targeting and probing

What it does not provide is conversational structure. That is why speech-heavy clips can still be:

- cut mid-thought
- merged without respecting turn changes
- scored without understanding whether one beat is complete

## Goals / Non-Goals

**Goals:**
- define a turn-level transcript structure from available transcript spans
- improve turn-aware snapping, merge, and split decisions
- make speech scoring aware of turn completeness

**Non-Goals:**
- full diarization accuracy
- cloud speech services
- multilingual dialogue semantics beyond what the local transcript backend can expose

## Decisions

### 1. Build turns from local transcript spans first

The first implementation should derive turns from available spans and silence/adjacency heuristics.

Why:
- the local backend already produces timed spans
- this can improve behavior before speaker diarization exists

### 2. Make turn structure optional but first-class

When available, turns should influence:

- refinement boundaries
- merge/split rules
- speech-mode evidence

When unavailable, the analyzer must keep current deterministic behavior.

### 3. Persist turn-aware provenance

Speech-heavy segments should record whether they were:

- snapped to turn edges
- merged across one turn
- split at a turn break

## Risks / Trade-offs

- derived turns may be imperfect on noisy footage
- turn heuristics can over-segment if they overreact to transcript gaps

## Migration Plan

1. Introduce transcript-turn data structures.
2. Derive turns from available transcript spans.
3. Apply turn-aware segmentation and scoring heuristics.
4. Add evaluation cases against the new harness.
