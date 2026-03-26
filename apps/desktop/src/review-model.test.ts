import test from "node:test";
import assert from "node:assert/strict";

import { buildSegmentReviewModel, deriveAnalysisPath } from "./review-model.ts";

test("buildSegmentReviewModel exposes winning recommendation details", () => {
  const model = buildSegmentReviewModel(
    {
      start_sec: 0,
      end_sec: 5,
      prefilter: {
        score: 0.9,
        shortlisted: true,
        filtered_before_vlm: false,
        selection_reason: "Reached VLM target set.",
        metrics_snapshot: { clip_score: 0.72 },
      },
      evidence_bundle: {
        keyframe_timestamps_sec: [1, 2.5, 4],
        context_window_start_sec: 0,
        context_window_end_sec: 10,
      },
      ai_understanding: {
        provider: "lmstudio",
        keep_label: "keep",
        confidence: 0.88,
        summary: "Strong winner.",
        rationale: "Clear narrative turn.",
      },
    },
    {
      is_best_take: true,
      selection_reason: "Won this clip at 67/100 on story alignment, hook strength, and speech ratio.",
      score_total: 0.67,
      score_technical: 0.48,
      score_semantic: 0.77,
      score_story: 0.77,
      outcome: "best",
      within_asset_rank: 1,
      score_gap_to_winner: 0,
      score_driver_labels: ["story alignment", "hook strength", "speech ratio"],
    },
  );

  assert.equal(model.outcomeLabel, "Best take");
  assert.equal(model.scoreValues.total, "67");
  assert.equal(model.rankLabel, "#1 in clip");
  assert.match(model.analysisPathSummary, /shortlisted/);
  assert.match(model.analysisPathSummary, /VLM lmstudio/);
});

test("deriveAnalysisPath covers blocked deterministic segments", () => {
  const path = deriveAnalysisPath({
    start_sec: 10,
    end_sec: 15,
    prefilter: {
      score: 0.63,
      shortlisted: true,
      filtered_before_vlm: true,
      selection_reason: "Stopped before VLM after CLIP gate.",
      clip_gated: true,
      metrics_snapshot: { clip_score: 0.21 },
    },
    evidence_bundle: {
      keyframe_timestamps_sec: [11],
      context_window_start_sec: 5,
      context_window_end_sec: 20,
    },
    ai_understanding: {
      provider: "deterministic",
      keep_label: "reject",
      confidence: 0.4,
      summary: "Fallback summary.",
      rationale: "Gated by CLIP.",
    },
  });

  assert.match(path, /CLIP 21/);
  assert.match(path, /CLIP gated/);
  assert.match(path, /deterministic fallback/);
});

test("buildSegmentReviewModel exposes provenance summaries", () => {
  const model = buildSegmentReviewModel(
    {
      start_sec: 1,
      end_sec: 5,
      review_state: {
        shortlisted: true,
        filtered_before_vlm: false,
        clip_scored: false,
        boundary_strategy_label: "Transcript snapped",
        boundary_confidence: 0.84,
        lineage_summary: "Merged 2 refined regions via transcript continuity.",
        semantic_validation_status: "validated",
        semantic_validation_summary: "Semantic validation kept the deterministic boundary at 81% confidence.",
      },
    },
    {
      is_best_take: false,
      selection_reason: "Kept as an alternate.",
      score_total: 0.64,
      outcome: "alternate",
      within_asset_rank: 2,
    },
  );

  assert.equal(model.provenance.boundaryLabel, "Transcript snapped");
  assert.equal(model.provenance.boundaryConfidence, "84% confidence");
  assert.match(model.provenance.lineageSummary, /Merged 2 refined regions/);
  assert.equal(model.provenance.semanticBadge, "Semantic validated");
});
