# Roadmap

## Purpose

This document tracks the likely next product directions for Roughcut Stdio beyond the current shipped analyzer baseline. It is intentionally higher level than an implementation proposal. The goal is to keep direction visible after individual changes are split, implemented, archived, or replaced.

## Implemented Baseline

- `deterministic-boundary-refinement`
- `narrative-unit-assembly`
- `semantic-boundary-validation`
- `segment-provenance-review`
- `transcript-backed-analysis`
- `segmentation-evaluation-harness`
- `transcript-turn-structure`
- `semantic-boundary-calibration`
- `cross-asset-story-assembly`

This baseline moved the analyzer from finding interesting snippets toward producing measurable, turn-aware editorial units and assembling a stronger first-pass rough cut across assets.

## Future Directions

### 1. Better Evaluation

The current fixture-driven evaluation harness is useful, but still narrow.

Likely next improvements:
- add more fixture sets by content type and difficulty
- track timeline-quality regressions, not only segment-shape regressions
- make benchmark output easier to compare across runs and releases
- define stronger quality metrics for “good rough cut” behavior

Why it matters:
- later tuning will get subjective again if quality is not measured broadly enough

### 2. Stronger Story Assembly

The current story assembly is a solid first heuristic pass, but it is still mostly rule-based.

Likely next improvements:
- better opener, middle, and release behavior across assets
- less adjacent repetition in beat type, role, and visual rhythm
- stronger use of the story prompt when shaping sequence flow
- better tradeoffs between locally strong clips and globally coherent sequences

Why it matters:
- the next product step is not just “better clips,” but “better cuts”

### 3. Better Speech Understanding

Transcript turns improved speech-heavy footage, but spoken structure is still only partially modeled.

Likely next improvements:
- better spoken-beat completeness
- stronger question/answer or setup/payoff grouping
- better monologue continuity
- optional future speaker-aware behavior if the product needs it

Why it matters:
- dialogue and interview footage still exposes the biggest structural weaknesses when speech understanding is too shallow

### 4. Runtime And Reliability

The analyzer is now more capable, but also more layered.

Likely next improvements:
- clearer runtime and cache reporting
- tighter control over expensive AI-path activation
- better fallback visibility in generated data and desktop review
- continued benchmark tuning for transcript, semantic, and assembly stages

Why it matters:
- product trust depends on the pipeline being predictable, debuggable, and fast enough to use regularly

### 5. Review And Editorial UX

Even without feedback learning, the desktop app can do more to explain and support editorial decisions.

Likely next improvements:
- clearer explanation of why the rough cut was assembled in that order
- better comparison of alternates at both segment and sequence level
- stronger provenance inspection for story-assembly decisions
- better review tools for sequence-level judgment instead of only clip-level judgment

Why it matters:
- once the analyzer proposes better cuts, the review surface becomes the main product interface for trust and iteration

### 6. Standalone Desktop Distribution

The product already has a real desktop app, but it still behaves like a development wrapper around the repository instead of a packaged application.

Likely next improvements:
- replace repo-relative setup and process assumptions with app-managed runtime orchestration
- bundle the analyzer runtime and required binaries as sidecars or packaged resources
- move generated output, logs, settings, and caches into app-managed storage
- add first-run bootstrap for optional transcript and local AI assets
- package, sign, and verify the app as a normal desktop product release

Why it matters:
- the current product experience is still too close to a developer environment
- a standalone app is the clearest path from “useful tool in a repo” to “real desktop product”

## Current Direction

There is no active chained analyzer follow-up in this area right now. Future work should be proposed from the current shipped baseline. The currently identified product-facing next step is [standalone-desktop-distribution](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-desktop-distribution/proposal.md).

## Guiding Principle

The analyzer should keep moving from:

- “find interesting windows”

toward:

- “propose usable editorial units”

and then from:

- “propose usable editorial units”

toward:

- “assemble and improve coherent rough-cut story structure”

Every future analyzer change should be evaluated against that progression.
