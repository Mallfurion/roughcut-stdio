## 1. Domain Model

- [x] 1.1 Add `clip_score` optional float field to the prefilter metrics snapshot schema in `domain.py` — present only when CLIP is enabled, absent otherwise
- [x] 1.2 Add `clip_gated` boolean field to `PrefilterDecision` in `domain.py` (default `False`) — set to `True` when a segment is excluded from VLM targeting by the CLIP gate
- [x] 1.3 Add `vlm_budget_capped` boolean field to `PrefilterDecision` — set to `True` when a segment is excluded from VLM targeting by the global budget cap rather than the CLIP gate

## 2. CLIP Scorer

- [x] 2.1 Create `services/analyzer/app/clip.py` with a `CLIPScorer` class that wraps `open_clip.create_model_and_transforms()`, caches text embeddings for the fixed positive and negative prompt sets on first use, and exposes a `score(image_path: str) -> float` method returning a normalized [0, 1] score
- [x] 2.2 Implement the scoring formula in `CLIPScorer.score()`: `clip_score = clamp(mean(positive_sims) - 0.5 × mean(negative_sims))`, normalized to [0, 1]
- [x] 2.3 Implement `CLIPScorer.is_available() -> bool` as a module-level function that returns `True` only when `open-clip-torch` is importable — used at startup to determine whether CLIP can run
- [x] 2.4 Implement graceful model loading: if `open_clip.create_model_and_transforms()` raises any exception, log the error and fall back to CLIP-disabled behavior without interrupting the pipeline
- [x] 2.5 Load the model once at the start of the CLIP scoring pass and hold it for the duration of the run; do not reload per asset or per segment

## 3. Configuration

- [x] 3.1 Add `TIMELINE_AI_CLIP_ENABLED` environment variable to the AI config loading in `ai.py` (default: `false`)
- [x] 3.2 Add `TIMELINE_AI_CLIP_MIN_SCORE` environment variable (default: `0.35`)
- [x] 3.3 Add `TIMELINE_AI_VLM_BUDGET_PCT` environment variable (default: `10`)
- [x] 3.4 Add optional `TIMELINE_AI_CLIP_MODEL` environment variable to select the `open-clip-torch` model name and pretrained weights (default: `ViT-B-32` / `laion2b_s34b_b79k`)

## 4. Pipeline Integration

- [x] 4.1 Modify evidence building in `analyze_assets()` in `analysis.py` (line ~324): change `extract_keyframes` condition from `segment.id in ai_target_ids` to `segment.id in prefilter_shortlist_ids` so keyframes are extracted for all shortlisted segments, not just VLM targets
- [x] 4.2 After evidence building completes, invoke the CLIP scoring pass when CLIP is enabled: iterate over all shortlisted segments with evidence bundles, score each one's contact sheet (or first keyframe if no contact sheet exists), set `clip_score` in the prefilter metrics snapshot, and mark segments below `TIMELINE_AI_CLIP_MIN_SCORE` as `clip_gated=True`
- [x] 4.3 Update VLM target selection to be a three-stage gate:
  - Stage 1: Filter out segments where `clip_gated=True`
  - Stage 2: Apply per-asset limit using `max_segments_per_asset` (existing logic)
  - Stage 3: Apply global VLM budget cap: compute `floor(total_candidates × TIMELINE_AI_VLM_BUDGET_PCT / 100)`, rank all eligible segments across all assets by composite score `(prefilter_score + clip_score) / 2.0`, select top-N, and mark remaining eligible segments as `vlm_budget_capped=True`
- [x] 4.4 Ensure `clip_gated` and `vlm_budget_capped` segments receive deterministic understanding (do not send to VLM analyzer) and appear in `generated/project.json` with their full prefilter record and selection reason

## 5. Scoring

- [x] 5.1 Update `scoring.py` to include `clip_score` as a semantic input in the visual score path when present in the metrics snapshot — weight it alongside `visual_novelty` and `hook_strength`
- [x] 5.2 Verify that when `clip_score` is absent (CLIP disabled), the scoring path is identical to the current behavior

## 6. Reporting

- [x] 6.1 Add CLIP and budget statistics to `project.analysis_summary`: `clip_scored_count`, `clip_gated_count`, `vlm_budget_cap_pct`, `vlm_budget_was_binding`, `vlm_target_pct_of_candidates`
- [x] 6.2 Extend process reporting in `scripts/process.sh` to print CLIP coverage and budget utilisation in the summary output and `generated/process.log`

## 7. Documentation

- [x] 7.1 Update `docs/analyzer-pipeline.md` to document the CLIP scoring step (Step 2.6) and the global VLM budget cap as part of the per-asset analysis phase
- [x] 7.2 Document `TIMELINE_AI_CLIP_ENABLED`, `TIMELINE_AI_CLIP_MIN_SCORE`, `TIMELINE_AI_VLM_BUDGET_PCT`, and `TIMELINE_AI_CLIP_MODEL` in the configuration table in `docs/analyzer-pipeline.md`

## 8. Validation

- [x] 8.1 Add unit tests for `CLIPScorer`: scoring formula, prompt embedding caching, `is_available()` returning `False` when `open-clip-torch` is not installed
- [x] 8.2 Add a test verifying that when `TIMELINE_AI_CLIP_ENABLED=false`, no `CLIPScorer` is instantiated and no `clip_score` fields appear in the output
- [x] 8.3 Add a test verifying that segments below `TIMELINE_AI_CLIP_MIN_SCORE` are marked `clip_gated=True` and do not appear in the VLM target set
- [x] 8.4 Add a test verifying that the global budget cap correctly marks `vlm_budget_capped=True` on the lowest-scoring segments when the cap is binding
- [x] 8.5 Add a test verifying that `vlm_budget_capped` and `clip_gated` segments receive deterministic understanding and appear in `generated/project.json`
- [x] 8.6 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [x] 8.7 Verify `npm run process` with `TIMELINE_AI_CLIP_ENABLED=false` produces output identical to the pre-change baseline
- [x] 8.8 Verify `npm run build:desktop` still succeeds
