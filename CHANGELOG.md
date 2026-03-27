# Changelog

## [Unreleased]

## [2.1.0] - 2026-03-28

### 🚀 Features

- Optimize analyzer runtime with run-scoped semantic validation budgets, evidence reuse, batched keyframe extraction, and clearer MLX execution reporting.
- Cache deterministic prefilter artifacts and batch deterministic frame and audio screening work to accelerate repeated process runs.

### 🛠 Fixes & Improvements

- Restyle the results header and make provenance and sequence sections collapsible in the review UI.
- Archive the completed performance proposals, sync the resulting OpenSpec specs, and refresh roadmap and proposal docs.
- Refresh the README app imagery.

## [2.0.1] - 2026-03-27

### 🚀 Features

- Add an ordering option for the results view.

### 🛠 Fixes & Improvements

- Add the runtime-performance-optimization proposal docs.

## [2.0.0] - 2026-03-27

### 🚀 Features

- Ship the standalone desktop app with bundled runtime, packaged processing/export orchestration, startup bootstrap, and app-managed storage.

### 🛠 Fixes & Improvements

- Default the project and desktop app to `mlx-vlm-local`, `mlx-community/Qwen3.5-0.8B-4bit`, `TIMELINE_AI_MODE=full`, and `TIMELINE_AI_CLIP_MIN_SCORE=0.1`.
- Serialize local MLX-VLM runtime calls on Metal for safer packaged execution.
- Refresh implementation docs, archive the completed standalone distribution change, and add follow-up proposals for desktop polish and runtime size optimization.

### 📦 Other

- Add the docs-sync skill workflow and refresh project branding assets.

## [1.6.0] - 2026-03-27

### 🚀 Features

- Add desktop best-take overrides and timeline preview controls to the review workflow.
- Harden runtime reliability handling in the desktop and analyzer flow.
- Improve speech understanding and cross-asset story assembly behavior.
- Expand the evaluation harness and story-assembly implementation.

### 🛠 Fixes & Improvements

- Archive completed OpenSpec proposals and specs.
- Add follow-up proposals for next steps and standalone desktop distribution.
- Clean up proposal docs and parent proposal references.

## [1.5.1] - 2026-03-27

### 🛠 Fixes & Improvements

- Split the desktop app into state, platform, render, and review modules to improve separation of concerns and maintainability.

## [1.5.0] - 2026-03-26

### 🚀 Features

- Stabilize semantic boundary calibration with transcript-turn-aware scoring, repeatable segmentation evaluation, stricter local split handling, and better semantic boundary diagnostics.

### 🛠 Fixes & Improvements

- Update analyzer and desktop configuration/docs for the new evaluation and semantic-boundary behavior.

### 📦 Other

- Archive the completed OpenSpec changes for segmentation evaluation, transcript-turn structure, and semantic-boundary calibration.

## [1.4.0] - 2026-03-26

### 🚀 Features

- Add transcript-backed analysis with local faster-whisper support, desktop controls, runtime reporting, and selective transcript probing.

### 🛠 Fixes & Improvements

- Lower the semantic boundary ambiguity threshold to 0.6 for better validation targeting.

## [1.3.1] - 2026-03-26

### 🛠 Fixes & Improvements

- Add segmentation settings to the desktop app.
- Default segmentation refinement and semantic validation to enabled.

## [1.3.0] - 2026-03-26

### 🚀 Features

- Refine segment selection with deterministic boundary refinement and narrative-unit assembly.
- Align the desktop review workspace with recommendation ranking, score breakdowns, and segment imagery.
- Add analyzer process benchmarking artifacts and run-history tracking.

### 🛠 Fixes & Improvements

- Update processing workflow documentation and supporting docs for the new review and benchmarking flow.

### 📦 Other

- Archive the implemented OpenSpec change proposals for segment refinement work.
- Merge pull request #2 from `feature/segment-refinement`.

## [1.2.0] - 2026-03-26

### 🚀 Features

#### Semantic Quality Filtering with CLIP

- Add CLIP-based semantic scoring to measure editorial quality of shortlisted segments
- Implement configurable quality gating via `TIMELINE_AI_CLIP_MIN_SCORE` (default 0.35)
- Support custom CLIP models via `TIMELINE_AI_CLIP_MODEL` (default: ViT-B-32)
- Gracefully degrade to histogram dedup when CLIP unavailable

#### Intelligent Segment Deduplication

- Implement CLIP embedding-based deduplication (cosine similarity ≥ 0.95)
- Add histogram fallback dedup for non-CLIP environments (configurable threshold)
- Deduplicate after prefilter scoring, before VLM analysis to eliminate redundant takes
- Track dedup statistics: group count and eliminated segment count in analysis summary

#### VLM Budget Controls

- Add `TIMELINE_AI_VLM_BUDGET_PCT` setting to cap Vision Language Model analysis depth
- Implement three-stage gating: dedup filter → CLIP quality gate → per-asset budget cap
- Route budget-capped segments to fast deterministic analysis instead
- Enable cost-proportional scaling for large projects

#### Audio-Aware Prefiltering

- Extract audio signals: RMS energy + silence detection (ffmpeg astats + silencedetect)
- Identify audio peaks as candidate segment windows alongside visual peaks
- Route segments as "speech" or "visual" mode for analysis
- Improve handling of interview-heavy and dialogue-centric footage

#### Enhanced UI & Configuration

- Add desktop app controls for clipEnabled, clipMinScore, vlmBudgetPct
- Document all configuration options in environment variable table

### 🛠 Fixes & Improvements

#### Pipeline Robustness

- Fix hard imports of optional CLIP dependencies (PIL, numpy) that broke non-CLIP installs
- Fix CLIPDeduplicator index bug that could silently pick wrong keeper when embeddings missing
- Fix histogram fallback dedup no-op by properly accumulating and passing frame signals
- Fix dedup reporting: preserve dedup-specific selection_reason instead of overwriting
- Fix apply_deduplication_results() to properly set selection_reason for deduplicated segments

#### Documentation & Observability

- Add comprehensive analyzer-pipeline.md documenting all four analysis phases
- Add architecture.md with design decisions and extensibility points
- Add configuration.md with all environment variable defaults and examples
- Include dedup group count and eliminated count in analysis_summary
- Improve segment selection_reason clarity for all filtering paths

### 📦 Other

- Organize analyzer enhancements with OpenSpec structured changes tracking
- All new features optional with graceful degradation (no breaking changes)

## [1.1.0] - 2026-03-25

### 🚀 Features

- Add Phase 1 AI detection capabilities for segment understanding.
- Add the vision prefilter pipeline to shortlist segments before VLM analysis.
- Add `moondream-local` setup as an intermediate embedded local VLM backend.
- Add `mlx-vlm-local` support and align the local MLX-VLM workflow.
- Implement the Tauri desktop app for folder selection, processing, review, and Resolve export.

### 🛠 Fixes & Improvements

- Improve process logging and AI runtime reporting.
- Consolidate docs into `docs/` and OpenSpec, and update the desktop-first workflow documentation.
- Refresh general documentation and configuration guidance.

### 📦 Other

- Rename the product to Roughcut Stdio.
- Add a repo-local `release` skill for semantic-versioned releases and changelog generation.

## [1.0.0] - 2026-03-24

### 🚀 Features

- Initial implementation of the local footage analysis and timeline generation workflow.

### 🛠 Fixes & Improvements

- Allow processing footage without proxy files.
- Fix timeline encoding and add environment-variable media folder support.
- Add project versioning for the first tagged release.
