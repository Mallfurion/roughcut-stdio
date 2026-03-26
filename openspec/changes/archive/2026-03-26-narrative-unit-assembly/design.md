## Context

The deterministic boundary-refinement change improves local start and end points, but it does not solve continuity by itself. Editors still need segments that correspond to complete beats, not isolated fragments. This change adds a narrative assembly step that can combine or divide refined regions before recommendation logic runs.

## Goals / Non-Goals

**Goals:**
- Merge adjacent refined regions when they clearly belong together
- Split refined regions that contain multiple ideas
- Recalculate metrics on final narrative units
- Preserve lineage so later review and debugging remain possible

**Non-Goals:**
- VLM-based boundary diagnosis
- Cross-asset story assembly
- Full review-surface provenance UI

## Decisions

### 1. Narrative assembly runs after deterministic refinement and before final scoring

The assembly stage consumes refined regions and outputs the final candidate segments used by ranking, take selection, and timeline generation.

Rationale:
- Scoring fragmented regions biases selection before continuity is resolved.
- Merge/split must operate on already bounded regions, not raw seeds.

### 2. First-pass assembly is deterministic and adjacency-bound

V1 assembly only considers adjacent refined regions from the same asset and uses deterministic evidence such as transcript continuity, silence-free turns, short temporal gaps, and scene-consistent continuity.

Rationale:
- Adjacent-within-asset assembly is predictable and testable.
- It covers the most common editorial failures without introducing speculative story logic.

### 3. Split rules are conservative

The pipeline will split a refined region only when there is strong evidence such as multiple transcript turns or a stable structural divider inside the region.

Rationale:
- Bad merges are reversible in later work; bad splits can destroy context too early.
- Conservative splitting keeps the output stable.

### 4. Merge and split lineage is persisted even before UI surfacing

Final assembled units will retain references to the refined regions they came from and the rule family that caused the merge or split.

Rationale:
- Lineage is needed for debugging, testing, and later review-surface work.

## Risks / Trade-offs

- [Assembly rules may over-merge dialogue or reactions] -> Start with tight adjacency and continuity thresholds.
- [Splits may become too aggressive] -> Require strong evidence and test speech-heavy examples carefully.
- [Metric recomputation adds complexity] -> Reuse existing aggregation paths instead of inventing parallel scoring logic.
