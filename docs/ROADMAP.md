# Roadmap

## Purpose

This document tracks the next major improvement areas for Roughcut Stdio beyond the current shipped segmentation foundation. It is intentionally higher level than an implementation proposal. The goal is to keep direction visible after individual changes are split, implemented, archived, or replaced.

## Current Analyzer Focus

The current segmentation foundation was delivered through four OpenSpec changes:

1. `deterministic-boundary-refinement`
2. `narrative-unit-assembly`
3. `semantic-boundary-validation`
4. `segment-provenance-review`

Those changes are now implemented and archived. They are now joined by four newer shipped improvements:

5. `segmentation-evaluation-harness`
6. `transcript-turn-structure`
7. `semantic-boundary-calibration`
8. `cross-asset-story-assembly`

Together, this baseline moves the analyzer from finding interesting snippets to producing measurable, turn-aware within-asset narrative units and assembling a stronger first-pass sequence across assets.

In practical terms, they aim to:

- stop treating cheap signal windows as final edit units
- refine boundaries using deterministic structure first
- merge or split adjacent regions into better editorial beats
- use semantic validation only for ambiguous cases
- expose segment provenance so editors can understand why a segment exists

## What The Current Baseline Covers

After the segmentation-foundation changes, the analyzer should be better at:

- reducing padded or truncated candidate segments
- preserving more complete dialogue and action beats within a clip
- forming cleaner candidate units before scoring and recommendation
- keeping AI-assisted refinement bounded and fallback-safe
- making segment-formation decisions inspectable in review

After the evaluation harness, turn-aware transcript work, and cross-asset assembly, the analyzer should also be better at:

- measuring segmentation quality against stable fixture sets
- aligning speech segments to complete spoken turns instead of only raw transcript spans
- preserving question/answer and continuous monologue flow more reliably
- exposing turn-aware provenance in generated project data and review
- selecting winning clips in relation to each other instead of only by per-asset score
- improving opener choice, alternation, and release beats across the assembled rough cut

## What They Do Not Fully Solve

Even after this current baseline, several important analyzer problems remain:

- long-term evaluation should expand beyond the current fixture set
- story assembly is still heuristic rather than feedback-informed
- editor feedback learning is intentionally deferred until the review workflow is more settled

## Current Direction

The post-segmentation chain is complete through cross-asset story assembly. There is no active follow-up proposal in this area right now. Future work in this part of the product should be proposed from the current baseline rather than assuming the previously planned feedback-learning step is still in scope.

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
