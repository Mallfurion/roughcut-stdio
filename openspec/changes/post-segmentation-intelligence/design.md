## Context

The current baseline already covers:

- deterministic boundary refinement
- narrative-unit assembly
- selective semantic boundary validation
- transcript-backed analysis with selective probing
- review provenance

What remains is not one feature. It is a sequence:

1. measure segmentation quality explicitly
2. improve transcript-turn structure
3. retune semantic validation against that richer evidence
4. assemble stronger cross-asset sequences
5. learn from editor behavior

## Decisions

### 1. Keep this change as an umbrella only

This change is a planning parent, not an implementation target.

Why:
- the remaining work spans multiple subsystems
- each step should be implemented and validated independently

### 2. Make dependencies explicit with `x-roughcut.depends_on`

The post-segmentation chain is:

1. `segmentation-evaluation-harness`
2. `transcript-turn-structure`
3. `semantic-boundary-calibration`
4. `cross-asset-story-assembly`
5. `editor-feedback-learning`

Why:
- evaluation should exist before deeper tuning
- transcript-turn structure should improve the evidence before semantic retuning
- sequence assembly should consume stronger units, not compensate for weak local structure
- feedback learning should come after the review and assembly behavior is stable enough to learn from

## Risks / Trade-offs

- an umbrella can become stale if child changes are not kept current
- the later changes may evolve as the evaluation harness reveals new bottlenecks

## Migration Plan

1. Create the child changes with chaining metadata.
2. Implement them in order unless new evidence suggests a dependency change.
3. Archive each child independently after implementation.
