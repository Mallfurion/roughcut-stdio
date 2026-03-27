## Why

The current analyzer is better at forming usable within-asset segments, but the next product bottlenecks are now clearer:

- segmentation quality is harder to measure consistently
- transcript evidence is still too coarse for dialogue-heavy footage
- semantic boundary validation is implemented but rarely activates in real runs
- project-level sequence assembly is still weak

This umbrella change captures the next chained phase after context-complete segmentation.

## What Changes

- Establish a chained post-segmentation roadmap for analyzer quality, speech structure, and story assembly.
- Split that roadmap into focused implementation changes so each phase can ship and be evaluated separately.
- Preserve the current pattern of `x-roughcut` dependency metadata to make rollout order explicit.

## Impact

- OpenSpec change planning under `openspec/changes/`
- Future analyzer, desktop, and benchmark work that builds on the current segmentation foundation
