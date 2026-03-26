## Context

The current semantic boundary pass is bounded and safe, but often inactive. That means:

- the capability exists but is not shaping real output
- ambiguous segments can still slip through untouched
- runtime cost is low partly because the feature is under-targeted

## Goals / Non-Goals

**Goals:**
- calibrate ambiguity scoring against measured outcomes
- activate semantic validation on the right subset of borderline segments
- preserve explicit runtime caps and deterministic fallback

**Non-Goals:**
- validating every segment
- replacing deterministic segmentation with model-only segmentation

## Decisions

### 1. Use evaluation metrics to calibrate ambiguity

The segmentation evaluation harness should be the first source of truth for calibration.

Why:
- semantic targeting should be evidence-driven, not intuition-driven

### 2. Introduce a bounded activation floor

If no segment crosses the primary threshold, the analyzer may still validate a very small number of the most ambiguous segments.

Why:
- completely dormant semantic validation is hard to evaluate and easy to neglect

### 3. Persist impact metadata

The analyzer should record whether semantic validation:

- changed nothing
- trimmed or extended a segment
- split a segment
- was skipped by threshold, budget, or provider state

## Risks / Trade-offs

- over-activation could erase the runtime advantage of bounded semantic validation
- under-activation preserves the current dormancy problem

## Migration Plan

1. Add evaluation-backed ambiguity reporting.
2. Retune thresholds and penalties.
3. Add a bounded minimum-target rule.
4. Re-evaluate runtime and quality against the harness.
