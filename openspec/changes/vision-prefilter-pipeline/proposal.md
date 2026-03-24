## Why

The current Phase 1 pipeline still spends too much time on local VLM inference. Even in fast mode, LM Studio is being used too early in the pipeline and too often per asset, which makes processing cost scale with segment count instead of with genuinely promising footage.

For this product, the first job is not deep semantic understanding. The first job is fast scoring and filtering: sample frames, identify strong visual regions, group them into candidate segments, suppress weak or repetitive material, and only then ask the VLM for final editorial input. This change aligns the implementation with that architecture so local processing becomes dramatically cheaper and the VLM becomes the last refinement step rather than the first screening step.

## What Changes

- Add a cheap pre-VLM visual screening stage that runs on every asset before any multimodal model call.
- Sample frames at low cost and score them using deterministic or lightweight vision signals such as sharpness, blur, motion, stability, subjectness proxies, composition proxies, distinctiveness, and optional CLIP or aesthetic-style embeddings.
- Build candidate regions from scene boundaries plus score peaks, motion changes, and deduplicated frame clusters instead of relying primarily on placeholder segment windows.
- Shortlist only the strongest candidate regions per asset for downstream VLM inspection.
- Move LM Studio to the last possible step so it only labels, compares, or explains already-filtered candidate segments.
- Persist prefilter scores and shortlist decisions into generated project state so the screening stage is inspectable and reusable.
- Expand runtime reporting to show how much footage was filtered before VLM, how many VLM requests were avoided, and where time was spent.
- Keep deterministic fallback behavior and Resolve-safe output intact while changing the internal recommendation pipeline.

## Capabilities

### New Capabilities
- `vision-prefilter-pipeline`: low-cost frame sampling, visual scoring, segment prefiltering, and shortlist generation before VLM analysis.

### Modified Capabilities
- `deterministic-screening`: replace placeholder-first candidate ranking with feature-driven visual prefiltering and shortlist construction.
- `ai-segment-understanding`: reposition VLM analysis as a late-stage refinement pass over shortlisted segments rather than the primary screening layer.
- `processing-workflow`: expand process-time reporting and artifacts to expose prefilter metrics, shortlist counts, and VLM reduction statistics.

## Impact

- Affected code:
  - `services/analyzer/app/analysis.py`
  - `services/analyzer/app/ai.py`
  - `services/analyzer/app/domain.py`
  - `services/analyzer/app/scoring.py`
  - media/frame extraction utilities and any new lightweight feature modules
  - process logging scripts
- Affected outputs:
  - `generated/project.json`
  - `generated/process.log`
  - generated analysis artifacts for cached prefilter features and shortlist evidence
- Dependencies and systems:
  - `ffmpeg` / `ffprobe`
  - `PySceneDetect`
  - `OpenCV` or equivalent cheap visual feature extraction
  - optional CLIP or aesthetic-style lightweight scoring
  - LM Studio request volume, batching strategy, and cache effectiveness

