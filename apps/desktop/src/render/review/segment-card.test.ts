import test from "node:test";
import assert from "node:assert/strict";

import type { Asset, CandidateSegment } from "../../app/types.ts";
import { renderSegmentCard } from "./segment-card.ts";

test("renderSegmentCard places sequence and provenance in the detail grid and omits the analysis path line", () => {
  const asset: Asset = {
    id: "asset-1",
    name: "Clip A",
    source_path: "/tmp/a.mov",
    has_proxy: false,
    has_speech: true,
    interchange_reel_name: "A001",
  };

  const segment: CandidateSegment = {
    id: "segment-1",
    asset_id: "asset-1",
    start_sec: 0,
    end_sec: 6,
    analysis_mode: "visual",
    description: "Scene snapped",
    transcript_excerpt: "",
    quality_metrics: {
      sharpness: 0.8,
      stability: 0.7,
      visual_novelty: 0.6,
      subject_clarity: 0.9,
      motion_energy: 0.5,
      duration_fit: 0.4,
      speech_presence: 0.3,
      hook_strength: 0.6,
      story_alignment: 0.7,
    },
    prefilter: {
      score: 0.88,
      shortlisted: true,
      filtered_before_vlm: false,
      selection_reason: "Strong visual beat.",
      metrics_snapshot: {
        clip_score: 0.32,
      },
    },
    evidence_bundle: {
      keyframe_paths: [],
      keyframe_timestamps_sec: [0, 2, 4, 5],
      context_window_start_sec: 0,
      context_window_end_sec: 6,
    },
    ai_understanding: {
      provider: "mlx-vlm-local",
      keep_label: "keep",
      confidence: 0.62,
      summary: "Alternates from speech to visual to keep sequence contrast.",
      rationale: "Adds role variety.",
      story_roles: [],
      shot_type: "wide",
      camera_motion: "static",
      mood: "calm",
      risk_flags: [],
    },
    review_state: {
      shortlisted: true,
      filtered_before_vlm: false,
      clip_scored: true,
      analysis_path_summary: "shortlisted -> CLIP 32 -> 4 keyframes -> VLM mlx-vlm-local",
      boundary_strategy_label: "Scene snapped",
      boundary_confidence: 0.62,
      lineage_summary: "Built from 1 seed region (visual peak).",
      semantic_validation_status: "not_eligible",
      semantic_validation_summary: "Deterministic boundaries were not ambiguous enough for semantic validation.",
    },
  };

  const html = renderSegmentCard(
    {
      segment,
      recommendation: {
        id: "take-1",
        candidate_segment_id: "segment-1",
        title: "Take 1",
        is_best_take: true,
        selection_reason: "Fits the story beat.",
        score_technical: 0.7,
        score_semantic: 0.8,
        score_story: 0.6,
        score_total: 0.72,
        outcome: "best",
        within_asset_rank: 1,
      },
      timelineItem: {
        sequence_group: "development",
        sequence_role: "visual bridge",
        sequence_score: 0.6,
        sequence_rationale: [
          "Alternates from speech to visual to keep sequence contrast.",
          "Adds role variety instead of repeating the same beat type.",
        ],
      },
    },
    asset,
  );

  assert.match(html, /section-detail-grid/);
  assert.match(html, /Sequence/);
  assert.match(html, /Provenance/);
  assert.doesNotMatch(html, /section-analysis-path/);
  assert.doesNotMatch(html, /shortlisted -&gt; CLIP 32 -&gt; 4 keyframes -&gt; VLM mlx-vlm-local/);
});

test("renderSegmentCard exposes promote and clear override controls with override provenance", () => {
  const asset: Asset = {
    id: "asset-1",
    name: "Clip A",
    source_path: "/tmp/a.mov",
    has_proxy: false,
    has_speech: true,
    interchange_reel_name: "A001",
  };

  const segment: CandidateSegment = {
    id: "segment-1",
    asset_id: "asset-1",
    start_sec: 0,
    end_sec: 6,
    analysis_mode: "visual",
    description: "Scene snapped",
    transcript_excerpt: "",
    quality_metrics: {
      sharpness: 0.8,
      stability: 0.7,
      visual_novelty: 0.6,
      subject_clarity: 0.9,
      motion_energy: 0.5,
      duration_fit: 0.4,
      speech_presence: 0.3,
      hook_strength: 0.6,
      story_alignment: 0.7,
    },
  };

  const backupHtml = renderSegmentCard(
    {
      segment,
      recommendation: {
        id: "take-backup",
        candidate_segment_id: "segment-1",
        title: "Take 1",
        is_best_take: false,
        baseline_is_best_take: true,
        selection_reason: "Analyzer pick.",
        score_total: 0.61,
        outcome: "backup",
        within_asset_rank: 2,
      },
    },
    asset,
    { allowOverrides: true, reviewBusy: false },
  );

  assert.match(backupHtml, /Mark As Best Take/);
  assert.match(backupHtml, /Analyzer pick/);

  const analyzerBestHtml = renderSegmentCard(
    {
      segment,
      recommendation: {
        id: "take-analyzer-best",
        candidate_segment_id: "segment-1",
        title: "Take 1",
        is_best_take: true,
        baseline_is_best_take: true,
        selection_reason: "Analyzer pick.",
        score_total: 0.72,
        outcome: "best",
        within_asset_rank: 1,
      },
    },
    asset,
    { allowOverrides: true, reviewBusy: false },
  );

  assert.match(analyzerBestHtml, /Clear Best Take/);
  assert.doesNotMatch(analyzerBestHtml, /Clear Override/);

  const overriddenHtml = renderSegmentCard(
    {
      segment,
      recommendation: {
        id: "take-best",
        candidate_segment_id: "segment-1",
        title: "Take 1",
        is_best_take: true,
        editor_override: true,
        selection_reason: "Editor override selected this take.",
        score_total: 0.61,
        outcome: "best",
        within_asset_rank: 2,
      },
    },
    asset,
    { allowOverrides: true, reviewBusy: false },
  );

  assert.match(overriddenHtml, /Clear Override/);
  assert.match(overriddenHtml, /Editor override/);

  const clearedHtml = renderSegmentCard(
    {
      segment,
      recommendation: {
        id: "take-cleared",
        candidate_segment_id: "segment-1",
        title: "Take 1",
        is_best_take: false,
        baseline_is_best_take: true,
        editor_cleared: true,
        selection_reason: "Editor cleared this clip from the timeline.",
        score_total: 0.72,
        outcome: "backup",
        within_asset_rank: 1,
      },
    },
    asset,
    { allowOverrides: true, reviewBusy: false },
  );

  assert.match(clearedHtml, /Mark As Best Take/);
  assert.match(clearedHtml, /Cleared from timeline/);
});
