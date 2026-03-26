# Roadmap

## Purpose

This document tracks the next major improvement areas for Roughcut Stdio beyond the current shipped segmentation foundation. It is intentionally higher level than an implementation proposal. The goal is to keep direction visible after individual changes are split, implemented, archived, or replaced.

The current post-segmentation roadmap is now also represented in OpenSpec under [post-segmentation-intelligence](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/post-segmentation-intelligence/proposal.md) with chained implementation-ready child changes.

## Current Analyzer Focus

The current segmentation foundation was delivered through four OpenSpec changes:

1. `deterministic-boundary-refinement`
2. `narrative-unit-assembly`
3. `semantic-boundary-validation`
4. `segment-provenance-review`

Those changes are now implemented and archived. Together, they move the analyzer from finding interesting snippets to producing usable within-asset narrative units.

In practical terms, they aim to:

- stop treating cheap signal windows as final edit units
- refine boundaries using deterministic structure first
- merge or split adjacent regions into better editorial beats
- use semantic validation only for ambiguous cases
- expose segment provenance so editors can understand why a segment exists

## What These Four Changes Cover

After these four changes, the analyzer should be better at:

- reducing padded or truncated candidate segments
- preserving more complete dialogue and action beats within a clip
- forming cleaner candidate units before scoring and recommendation
- keeping AI-assisted refinement bounded and fallback-safe
- making segment-formation decisions inspectable in review

## What They Do Not Fully Solve

Even after these four changes, several important analyzer problems remain:

- segmentation quality is still hard to measure consistently
- transcript evidence is still too coarse for many dialogue-heavy clips
- semantic boundary validation is implemented but underused in real runs
- cross-asset story assembly is still weak
- editor review actions are still not captured as reusable feedback

## Current Chained Roadmap

The next phase after the current shipped segmentation and transcript baseline is now split into the following chained OpenSpec changes:

1. [segmentation-evaluation-harness](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/segmentation-evaluation-harness/proposal.md)
2. [transcript-turn-structure](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/transcript-turn-structure/proposal.md)
3. [semantic-boundary-calibration](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/semantic-boundary-calibration/proposal.md)
4. [cross-asset-story-assembly](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/cross-asset-story-assembly/proposal.md)
5. [editor-feedback-learning](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/editor-feedback-learning/proposal.md)

This sequence is deliberate:

- evaluation comes first so future tuning is measurable
- transcript-turn structure improves the evidence before deeper semantic retuning
- semantic calibration happens after turn-aware evidence exists
- cross-asset story assembly builds on stronger within-asset units
- feedback learning comes last, once review and assembly behavior are stable enough to learn from

## Current Planned Changes

### 1. Segmentation Evaluation Harness

Proposal:
- [segmentation-evaluation-harness](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/segmentation-evaluation-harness/proposal.md)

Focus:
- define stable fixture sets
- persist comparable segmentation-quality metrics
- make future tuning measurable

### 2. Transcript Turn Structure

Proposal:
- [transcript-turn-structure](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/transcript-turn-structure/proposal.md)

Focus:
- expose turn-level transcript structure
- improve speech-heavy merge and split decisions
- score spoken segments with turn completeness in mind

### 3. Semantic Boundary Calibration

Proposal:
- [semantic-boundary-calibration](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/semantic-boundary-calibration/proposal.md)

Focus:
- calibrate ambiguity scoring with real evaluation data
- activate semantic validation on the right borderline segments
- keep runtime bounded while making the feature materially useful

### 4. Cross-Asset Story Assembly

Proposal:
- [cross-asset-story-assembly](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/cross-asset-story-assembly/proposal.md)

Focus:
- move from good local segments to stronger project-level sequencing
- score relationships across assets
- improve rough timeline ordering and grouping

### 5. Editor Feedback Learning

Proposal:
- [editor-feedback-learning](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/editor-feedback-learning/proposal.md)

Focus:
- capture editor review and timeline adjustments
- persist them as local feedback records
- use repeated patterns to improve later heuristics

## Planned Order

The active chained order is:

1. Segmentation evaluation harness
2. Transcript turn structure
3. Semantic boundary calibration
4. Cross-asset story assembly
5. Editor feedback learning

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
