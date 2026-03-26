## Context

The project now has:

- review provenance
- transcript-aware segmentation
- a path toward project-level story assembly

What it still lacks is a feedback loop. The analyzer proposes, but repeated editor corrections are not captured in a reusable way.

## Goals / Non-Goals

**Goals:**
- capture explicit editor actions as local feedback data
- persist feedback in a form the analyzer can reuse later
- keep the editor override path primary

**Non-Goals:**
- opaque model retraining
- remote analytics collection
- replacing user decisions with automatic learning

## Decisions

### 1. Record feedback before adapting heuristics

The first version should capture:

- accepted recommendation
- rejected recommendation
- trim adjustment
- reordered timeline item
- preferred alternate candidate

Why:
- high-quality capture is a prerequisite for safe reuse

### 2. Keep feedback local-first

Feedback should stay in local project data or adjacent local artifacts.

### 3. Adapt heuristics in bounded ways

Initial heuristic learning should be modest and explainable, such as:

- down-weighting repeatedly rejected segment shapes
- preferring boundary strategies that editors repeatedly keep
- adjusting sequence heuristics when a certain order is consistently changed

## Risks / Trade-offs

- noisy user behavior can produce misleading feedback
- heuristic adaptation can become hard to reason about if it is not transparent

## Migration Plan

1. Capture feedback events in review and timeline workflows.
2. Persist them locally.
3. Add bounded heuristic readers for repeated patterns.
4. Surface learned adjustments transparently in review or diagnostics.
