## Context

Current improvements are mostly local to one asset:

- better boundaries
- better narrative units
- better speech evidence

What is still weak is project-level assembly:

- good clips may be adjacent without forming a good sequence
- the timeline can feel like a bag of winners rather than a shaped cut

## Goals / Non-Goals

**Goals:**
- add sequence-level scoring across assets
- improve timeline ordering and grouping
- preserve transparent editorial rationale in review

**Non-Goals:**
- full automatic film editing
- removing editor control over order and trims

## Decisions

### 1. Build on final candidate units, not raw clips

Cross-asset assembly must consume the best within-asset units from earlier changes.

### 2. Prefer bounded sequence heuristics first

The first implementation should use deterministic and metadata-driven sequence scoring:

- role variety
- transition compatibility
- speech/visual alternation
- diversity across assets

### 3. Persist sequence rationale for review

If the analyzer reorders or groups clips because of sequence-level logic, that rationale must be visible.

## Risks / Trade-offs

- sequence scoring can become arbitrary if it is not grounded in explicit heuristics
- story assembly can conflict with take-level ranking if priorities are unclear

## Migration Plan

1. Add sequence-level scoring primitives.
2. Integrate them into timeline assembly.
3. Surface sequence rationale in review.
4. Validate sequence quality against representative projects.
