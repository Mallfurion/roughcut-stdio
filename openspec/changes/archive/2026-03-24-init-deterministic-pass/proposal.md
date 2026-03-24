## Why

The repository already has a working baseline for local footage screening, deterministic timeline generation, Resolve export, and optional Phase 1 AI segment understanding. That baseline is currently described across `plan/` documents, which makes the implemented state hard to distinguish from future work.

This change captures the shipped baseline in OpenSpec so the project has a canonical record of what exists today before future AI-driven ranking and story-planning changes build on top of it.

## What Changes

- Document the npm-first repository workflow around `setup`, `process`, `view`, `export`, and `check:ai`.
- Capture the implemented deterministic screening pipeline: media discovery, proxy matching, source-only fallback, candidate segment generation, deterministic scoring, take recommendation, and rough timeline assembly.
- Capture the implemented review surface in the web app for generated projects, timeline inspection, and export access.
- Capture the implemented Resolve handoff through generated timeline JSON and `FCPXML` export.
- Capture the implemented Phase 1 and Phase 1.5 AI layer: structured segment understanding, LM Studio integration, deterministic fallback, fast/full runtime modes, cache, and runtime reporting.
- Move the implemented planning baseline out of ad hoc `plan/` status notes and into an OpenSpec change that can serve as the historical baseline for later changes.

## Capabilities

### New Capabilities
- `processing-workflow`: npm-first setup, processing, viewing, export, environment configuration, and runtime reporting.
- `deterministic-screening`: source/proxy ingestion, candidate segment discovery, deterministic scoring, take recommendation, and rough timeline generation.
- `review-workspace`: browser review of the generated project, recommended segments, AI annotations, and rough timeline state.
- `resolve-export`: export of the generated timeline into Resolve-usable `FCPXML` with relinkable source references.
- `ai-segment-understanding`: optional LM Studio-backed segment understanding with deterministic fallback and optimized local runtime controls.

### Modified Capabilities

- None.

## Impact

- Affected documentation:
  - `openspec/changes/init-deterministic-pass/**`
  - `plan/README.md`
- Affected systems captured by this baseline:
  - npm command workflow
  - Python analyzer
  - Next.js review app
  - generated project/timeline artifacts
  - LM Studio integration path
  - Resolve export path
