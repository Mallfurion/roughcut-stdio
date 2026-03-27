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
- `standalone-desktop-distribution`

This baseline moved the analyzer from finding interesting snippets toward producing measurable, turn-aware editorial units and assembling a stronger first-pass rough cut across assets. It also established a real packaged standalone desktop runtime with app-managed storage, bundled runtime dependencies, packaged processing/export orchestration, and first-launch model bootstrap.

## Future Directions

### 1. Better Evaluation

Proposal:
- [evaluation-harness-expansion](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/evaluation-harness-expansion/proposal.md)

The current fixture-driven evaluation harness is useful, but still narrow.

Likely next improvements:
- add more fixture sets by content type and difficulty
- track timeline-quality regressions, not only segment-shape regressions
- make benchmark output easier to compare across runs and releases
- define stronger quality metrics for “good rough cut” behavior

Why it matters:
- later tuning will get subjective again if quality is not measured broadly enough

### 2. Stronger Story Assembly

Proposal:
- [story-assembly-improvements](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/story-assembly-improvements/proposal.md)

The current story assembly is a solid first heuristic pass, but it is still mostly rule-based.

Likely next improvements:
- better opener, middle, and release behavior across assets
- less adjacent repetition in beat type, role, and visual rhythm
- stronger use of the story prompt when shaping sequence flow
- better tradeoffs between locally strong clips and globally coherent sequences

Why it matters:
- the next product step is not just “better clips,” but “better cuts”

### 3. Better Speech Understanding

Proposal:
- [speech-understanding-improvements](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/speech-understanding-improvements/proposal.md)

Transcript turns improved speech-heavy footage, but spoken structure is still only partially modeled.

Likely next improvements:
- better spoken-beat completeness
- stronger question/answer or setup/payoff grouping
- better monologue continuity
- optional future speaker-aware behavior if the product needs it

Why it matters:
- dialogue and interview footage still exposes the biggest structural weaknesses when speech understanding is too shallow

### 4. Runtime And Reliability

Proposal:
- [runtime-reliability-hardening](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/runtime-reliability-hardening/proposal.md)

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

### 6. Standalone Desktop Polish

Proposal:
- [standalone-desktop-polish](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-desktop-polish/proposal.md)

The standalone desktop runtime now exists, but it still feels like a first shipped build rather than a polished desktop product.

Likely next improvements:
- add an installed-app runtime management surface for runtime health, downloaded assets, storage usage, and repair actions
- add first-launch migration/import for repo-local settings and generated runs
- add a packaged run library so prior runs can be reopened instead of only the active/latest run
- harden DMG generation and release verification so packaged output is reliable and repeatable

Why it matters:
- a packaged app still needs recovery, migration, and release reliability to feel production-ready
- reopening prior runs and repairing runtime state are product behaviors, not just tooling niceties

### 7. Standalone Runtime Size Optimization

Proposal:
- [standalone-runtime-size-optimization](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-runtime-size-optimization/proposal.md)

The standalone app is now functionally complete, but the packaged bundle is still too large for a normal desktop distribution workflow.

Likely next improvements:
- redefine the install around a slim deterministic core instead of bundling every optional runtime dependency
- move transcript, CLIP, and MLX-VLM support into downloadable runtime packs
- replace whole-`.venv` packaging with a runtime-only Python environment built for the app
- prune the packaged Python home and bundled runtime payload aggressively
- enforce bundle-size auditing and budgets in release verification

Why it matters:
- large installers slow down downloads, updates, release validation, and distribution
- a smaller core app will make the standalone product easier to ship and easier to trust operationally

## Current Direction

The current planned analyzer follow-up remains split into four concrete proposals:

1. [evaluation-harness-expansion](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/evaluation-harness-expansion/proposal.md)
2. [story-assembly-improvements](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/story-assembly-improvements/proposal.md)
3. [speech-understanding-improvements](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/speech-understanding-improvements/proposal.md)
4. [runtime-reliability-hardening](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/runtime-reliability-hardening/proposal.md)

The current product-facing desktop follow-up is now split into two concrete proposals:

1. [standalone-desktop-polish](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-desktop-polish/proposal.md)
2. [standalone-runtime-size-optimization](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-runtime-size-optimization/proposal.md)

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
