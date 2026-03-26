## Context

This change builds on deterministic refinement and narrative assembly. Its job is narrow: only resolve the cases where local structure cannot confidently tell whether a segment is complete, incomplete, or internally mixed. It should improve difficult cases without making the whole system expensive or fragile.

## Goals / Non-Goals

**Goals:**
- Use semantic boundary validation only on ambiguous segments
- Keep the feature opt-in and runtime-bounded
- Preserve deterministic output whenever AI cannot or should not run
- Persist enough metadata to explain when semantic validation changed a segment

**Non-Goals:**
- Replacing the primary segment-understanding pass
- Running extra AI on every candidate segment
- Full provenance review UI

## Decisions

### 1. Boundary validation is a separate pass from initial understanding

Semantic boundary validation will use a dedicated prompt and response schema rather than overloading the initial understanding call.

Rationale:
- It isolates boundary reasoning from general content description.
- It makes failures and budget behavior easier to inspect.

### 2. Only ambiguous segments are eligible

Eligibility will depend on deterministic boundary confidence and explicit ambiguity signals from the refinement and assembly stages.

Rationale:
- Most segments do not justify an extra AI call.
- This keeps cost proportional to ambiguity, not segment volume.

### 3. Budget caps are enforced before calls are made

The analyzer will support a configurable percentage or count cap and will skip semantic validation beyond that budget while recording skip reasons.

Rationale:
- Runtime cost should be predictable before model work starts.

### 4. Semantic results can recommend extend, trim, split, or keep

The boundary-validation schema will support bounded decision types without requiring a full re-analysis pass.

Rationale:
- The semantic stage should refine boundary decisions, not rebuild the whole segment model.

## Risks / Trade-offs

- [Prompt quality may be unstable across models] -> Use a constrained JSON schema and narrow decision space.
- [Budget selection may hide good improvements] -> Persist skip reasons and ambiguity scores for tuning.
- [Semantic overrides may conflict with deterministic structure] -> Bound changes to nearby regions and preserve fallback-safe defaults.
