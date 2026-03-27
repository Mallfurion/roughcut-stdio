# Roadmap

## Purpose

This document tracks future product work for Roughcut Stdio. It intentionally excludes shipped or archived changes so the roadmap stays focused on what is still ahead.

## Active Roadmap

### 1. Standalone Desktop Polish

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

### 2. Standalone Runtime Size Optimization

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

### 3. Review And Editorial UX

This remains a likely follow-up area, but it is not yet split into an active OpenSpec proposal.

Likely next improvements:
- clearer explanation of why the rough cut was assembled in that order
- better comparison of alternates at both segment and sequence level
- stronger provenance inspection for story-assembly decisions
- better review tools for sequence-level judgment instead of only clip-level judgment

Another likely follow-up area is deeper analyzer throughput work beyond the completed runtime and deterministic-preprocessing passes, for example:
- media-discovery parallelism
- bounded asset-level front-half parallelism
- batched CLIP scoring
- re-evaluating the two-stage dedup flow

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
