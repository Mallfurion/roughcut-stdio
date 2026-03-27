# Roadmap

## Purpose

This document tracks future product work for Roughcut Stdio. It intentionally excludes shipped or archived changes so the roadmap stays focused on what is still ahead.

## Active Roadmap

### 1. Runtime Performance Optimization

Proposal:
- [runtime-performance-optimization](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/runtime-performance-optimization/proposal.md)

Current focus:
- enforce semantic boundary validation as a true run-scoped budget
- reduce avoidable evidence regeneration and per-segment `ffmpeg` fan-out
- make MLX-local runtime reporting reflect configured and effective execution behavior
- improve benchmark output so cold-path versus warm-path performance is easier to compare
- keep the touched runtime-reporting paths lean while those diagnostics expand

Why it matters:
- local AI analysis is only practical if cold runs are predictable and affordable
- benchmark data needs to describe real runtime behavior, not just nominal settings

### 2. Deterministic Prefilter Acceleration

Proposal:
- [deterministic-prefilter-acceleration](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/deterministic-prefilter-acceleration/proposal.md)

Current focus:
- batch deterministic frame extraction so prefilter sampling stops paying one `ffmpeg` process per timestamp
- consolidate deterministic audio screening into one shared bounded asset pass
- persist reusable deterministic preprocessing artifacts for scene, frame, and audio screening inputs
- make benchmark output distinguish deterministic preprocessing warmth from AI-cache warmth

Why it matters:
- the biggest remaining cold-path cost still sits in the deterministic front half of the analyzer
- repeat runs should not rebuild the same low-cost screening artifacts when the media and relevant settings have not changed

### 3. Standalone Desktop Polish

Proposal:
- [standalone-desktop-polish](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-desktop-polish/proposal.md)

Current focus:
- add first-launch import and migration from repo-local settings and generated state
- add a packaged run library so previous runs can be reopened from app-managed storage
- add runtime-management surfaces for runtime health, assets, storage, and repair actions
- harden `.app` and DMG packaging so release output is reliable and repeatable

Why it matters:
- the packaged app needs recovery, migration, and reopenability to feel like a real desktop product
- release output needs to be dependable before packaged distribution becomes routine

### 4. Standalone Runtime Size Optimization

Proposal:
- [standalone-runtime-size-optimization](/Users/florin/Projects/personal/roughcut-stdio/openspec/changes/standalone-runtime-size-optimization/proposal.md)

Current focus:
- define a slim deterministic core bundle instead of shipping every optional dependency up front
- move transcript, CLIP, and MLX-VLM support into installable runtime packs
- replace whole-`.venv` packaging with a runtime-only packaged Python environment
- add bundle-size auditing, budgets, and verification for desktop releases

Why it matters:
- large bundles slow down downloads, installs, updates, and release verification
- a smaller deterministic core makes the desktop product easier to ship and easier to trust operationally

## Next Horizon

### 5. Review And Editorial UX

This remains a likely follow-up area, but it is not yet split into an active OpenSpec proposal.

Likely next improvements:
- clearer explanation of why the rough cut was assembled in that order
- better comparison of alternates at both segment and sequence level
- stronger provenance inspection for story-assembly decisions
- better review tools for sequence-level judgment instead of only clip-level judgment

Why it matters:
- once the analyzer and packaged runtime are more stable, the review surface becomes the main product interface for trust and iteration

## Guiding Principle

Future work should keep moving the product from:

- “propose usable editorial units”

toward:

- “assemble, explain, and improve coherent rough-cut story structure”

and from:

- “ship a functioning desktop runtime”

toward:

- “ship a desktop product that is reliable, recoverable, and lightweight enough to use routinely”
