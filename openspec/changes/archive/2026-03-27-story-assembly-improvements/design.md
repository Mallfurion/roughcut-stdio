## Context

The current story-assembly layer already moved the product beyond pure per-asset winner selection, but it is still mostly a bounded heuristic pass. It can produce a cleaner first rough cut, yet it still has obvious limitations around repeated beat types, weak opener choices, rough transitions, and insufficient use of the story prompt when multiple plausible sequences exist.

Improving this layer is now the clearest product-facing next step after the segmentation foundation.

## Goals / Non-Goals

**Goals:**
- Improve project-level sequence construction across assets.
- Reduce adjacent repetition and weak pacing in the assembled timeline.
- Use story-prompt fit more meaningfully during assembly.
- Preserve sequence rationale and diagnostics for inspection and tuning.

**Non-Goals:**
- Building a fully interactive sequence editor.
- Learning from editor feedback in this change.
- Replacing deterministic assembly with a model-only sequencing system.

## Decisions

### 1. Keep story assembly heuristic and inspectable

Story assembly will remain a deterministic scoring-and-selection layer rather than a freeform generative sequencing system.

Rationale:
- The product still needs predictable, debuggable output.
- Heuristic improvements can be measured and tuned with the evaluation harness.

Alternatives considered:
- Use a model to generate the entire rough cut order directly: rejected because it would reduce inspectability and make fallback behavior weaker.

### 2. Score sequence quality across multiple dimensions

The assembly pass will explicitly score or rank candidate sequence choices using factors such as:
- opener strength
- role or mode variety
- adjacent repetition avoidance
- prompt-fit
- release or outro suitability

Rationale:
- The current layer is too coarse to distinguish a merely acceptable sequence from a stronger one.

Alternatives considered:
- Tune only per-asset winner scores: rejected because the main problem is inter-clip fit, not only local clip quality.

### 3. Persist richer sequence rationale

Generated project state and process diagnostics will preserve the factors that shaped the final sequence so assembly changes stay reviewable and benchmarkable.

Rationale:
- Sequence tuning without explanation becomes difficult to trust.
- This also supports evaluation expansion and future UI improvements without requiring them in this change.

## Risks / Trade-offs

- [More heuristic dimensions can become opaque] -> Persist rationale and keep the scoring factors bounded and named.
- [Assembly may over-prioritize diversity over clip strength] -> Keep local segment strength as a first-class input rather than letting sequence variety dominate all decisions.
- [Prompt-aware assembly may become brittle] -> Use prompt fit as one factor, not as an absolute controller.

## Migration Plan

1. Extend sequence scoring to account for stronger pacing and repetition control.
2. Add richer sequence rationale to generated project and process artifacts.
3. Evaluate against broader fixture sets before promoting new heuristics aggressively.

## Open Questions

- Which assembly factors should be hard constraints versus soft scoring signals?
- Should opener and release selection be globally optimized or chosen with simpler position-specific rules?
