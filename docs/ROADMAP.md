# Roadmap

## Purpose

This document tracks the next major improvement areas for Roughcut Stdio beyond the currently active OpenSpec changes. It is intentionally higher level than an implementation proposal. The goal is to keep direction visible after individual changes are split, implemented, archived, or replaced.

## Current Analyzer Focus

The current segmentation overhaul is split into four OpenSpec changes:

1. `deterministic-boundary-refinement`
2. `narrative-unit-assembly`
3. `semantic-boundary-validation`
4. `segment-provenance-review`

Together, these changes are meant to move the analyzer from finding interesting snippets to producing usable within-asset narrative units.

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

- cross-asset story assembly
- speaker-aware dialogue structure
- richer transcript-turn understanding
- evaluation and benchmarking for segment quality
- learning from editor corrections and review choices
- finer-grained temporal evidence when current sampling is too coarse

These are likely the next major improvement areas once the current segmentation work is implemented and stabilized.

## Next Likely Roadmap Areas

### 1. Transcript Turn Structure

Improve how speech-heavy footage is segmented by working with turn-level transcript structure rather than excerpt text alone.

Likely goals:

- expose timed transcript spans or turns as a first-class analyzer input
- detect turn boundaries and speaker alternation where possible
- improve dialogue-unit grouping beyond silence-gap heuristics

Why this matters:

- many incomplete or awkward cuts in interviews and conversations come from weak turn awareness rather than weak visual boundaries

### 2. Segmentation Evaluation Harness

Add a repeatable way to measure segmentation quality so future changes can be tuned against something concrete.

Likely goals:

- define benchmark fixtures for speech-heavy, silent, montage, and mixed-content footage
- track metrics such as truncation rate, padding rate, merge precision, and narrative-unit completeness
- make analyzer changes comparable over time

Why this matters:

- once segmentation logic becomes more layered, intuition alone is not enough to judge regressions or gains

### 3. Cross-Asset Story Assembly

Move from producing strong within-asset units to producing stronger project-level story sequences.

Likely goals:

- identify relationships across assets, not just within a clip
- improve ordering and grouping of recommended units in the rough timeline
- better distinguish “good standalone segment” from “good segment for this sequence”

Why this matters:

- the current segmentation overhaul improves input units, but the rough cut still needs better multi-asset sequencing logic

### 4. Editor Feedback Learning

Learn from what the editor accepts, rejects, trims, or rearranges.

Likely goals:

- capture user corrections and review actions
- feed those decisions back into segmentation and ranking heuristics
- gradually improve defaults without removing editor control

Why this matters:

- provenance and review visibility create the foundation for actual feedback-driven improvement

## Suggested Order After The Current Four Changes

The most likely next sequence is:

1. Transcript turn structure
2. Segmentation evaluation harness
3. Cross-asset story assembly
4. Editor feedback learning

This order keeps the project grounded:

- first improve the evidence
- then improve measurement
- then improve sequence-level intelligence
- then learn from editor behavior

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
