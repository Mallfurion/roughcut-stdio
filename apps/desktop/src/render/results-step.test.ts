import test from "node:test";
import assert from "node:assert/strict";

import { renderResultsStep } from "./results-step.ts";
import type { AppState, CandidateSegment, LoadedProject } from "../app/types.ts";

function buildCandidateSegments(): CandidateSegment[] {
  return [
    {
      id: "segment-1",
      asset_id: "asset-1",
      start_sec: 0,
      end_sec: 4,
      analysis_mode: "visual",
      description: "Segment 1",
      transcript_excerpt: "",
      evidence_bundle: {
        keyframe_paths: ["/tmp/segment-1.jpg"],
        keyframe_timestamps_sec: [0],
        context_window_start_sec: 0,
        context_window_end_sec: 4,
      },
      quality_metrics: {
        sharpness: 0,
        stability: 0,
        visual_novelty: 0,
        subject_clarity: 0,
        motion_energy: 0,
        duration_fit: 0,
        speech_presence: 0,
        hook_strength: 0,
        story_alignment: 0,
      },
    },
    {
      id: "segment-2",
      asset_id: "asset-1",
      start_sec: 4,
      end_sec: 8,
      analysis_mode: "visual",
      description: "Segment 2",
      transcript_excerpt: "",
      evidence_bundle: {
        keyframe_paths: ["/tmp/segment-2.jpg"],
        keyframe_timestamps_sec: [4],
        context_window_start_sec: 4,
        context_window_end_sec: 8,
      },
      quality_metrics: {
        sharpness: 0,
        stability: 0,
        visual_novelty: 0,
        subject_clarity: 0,
        motion_energy: 0,
        duration_fit: 0,
        speech_presence: 0,
        hook_strength: 0,
        story_alignment: 0,
      },
    },
    {
      id: "segment-3",
      asset_id: "asset-1",
      start_sec: 8,
      end_sec: 12,
      analysis_mode: "visual",
      description: "Segment 3",
      transcript_excerpt: "",
      quality_metrics: {
        sharpness: 0,
        stability: 0,
        visual_novelty: 0,
        subject_clarity: 0,
        motion_energy: 0,
        duration_fit: 0,
        speech_presence: 0,
        hook_strength: 0,
        story_alignment: 0,
      },
    },
  ];
}

function buildAppState(): AppState {
  const appState: AppState = {
    currentStep: "results",
    mediaDir: "",
    aiMode: "fast",
    settings: null,
    settingsDraft: null,
    settingsOpen: false,
    settingsBusy: false,
    settingsMessage: "",
    mediaSummary: null,
    mediaSummaryError: "",
    runtimeCheck: null,
    runtimeBusy: false,
    runtimeMessage: "",
    process: {
      running: false,
      status: "idle",
      processed: 0,
      total: 0,
      current_asset: "",
      elapsed: "00:00",
      eta: "00:00",
      logs: [],
      output_path: null,
      error: null,
    },
    processLogsExpanded: false,
    expandedClipIds: [],
    expandedDetailPanelIds: [],
    allClipsExpanded: false,
    project: null,
    reviewBusy: false,
    exportPath: "",
    exportBusy: false,
    exportMessage: "",
    timelinePreviewOpen: false,
    resultsOrdering: "clip",
  };
  return appState;
}

function buildProject(): LoadedProject {
  const candidateSegments = buildCandidateSegments();
  const project: LoadedProject = {
    source: "generated",
    file_path: "/tmp/project.json",
    project: {
      project: {
        name: "Demo",
        story_prompt: "Prompt",
        status: "ready",
        analysis_summary: {
          runtime_reliability_mode: "degraded",
          runtime_reliability_summary: "AI active, transcript partial, semantic degraded, cache active",
          ai_runtime_mode: "active",
          transcript_runtime_mode: "partial",
          semantic_boundary_runtime_mode: "degraded",
          cache_runtime_mode: "active",
          runtime_degraded_reasons: ["transcript fallback on 1 asset"],
          runtime_intentional_skip_reasons: ["AI analysis skipped 3 segments before live VLM"],
          ai_live_segment_count: 1,
          ai_cached_segment_count: 2,
        },
      },
      assets: [
        {
          id: "asset-1",
          name: "Clip A",
          source_path: "/tmp/a.mov",
          has_speech: true,
          interchange_reel_name: "A001",
        },
      ],
      candidate_segments: candidateSegments,
      take_recommendations: [
        {
          id: "take-1",
          candidate_segment_id: "segment-2",
          title: "Bridge",
          is_best_take: true,
          selection_reason: "Best bridge",
          score_total: 0.8,
        },
        {
          id: "take-2",
          candidate_segment_id: "segment-1",
          title: "Opener",
          is_best_take: false,
          selection_reason: "Best opener",
          score_total: 0.7,
        },
      ],
      timeline: {
        id: "timeline-1",
        version: 1,
        story_summary: "Summary",
        items: [
          {
            id: "timeline-item-1",
            take_recommendation_id: "take-2",
            trim_in_sec: 0,
            trim_out_sec: 4,
            label: "Opener",
            notes: "",
            source_asset_path: "/tmp/a.mov",
            source_reel: "A001",
          },
          {
            id: "timeline-item-2",
            take_recommendation_id: "take-1",
            trim_in_sec: 0,
            trim_out_sec: 4,
            label: "Bridge",
            notes: "",
            source_asset_path: "/tmp/a.mov",
            source_reel: "A001",
          },
        ],
      },
    },
  };
  return project;
}

test("renderResultsStep keeps only the compact top-level metrics in the summary header", () => {
  const appState = buildAppState();
  const project = buildProject();
  appState.project = project;

  const html = renderResultsStep(appState);

  assert.match(html, /Preview Timeline/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /class="view-head results-head"/);
  assert.match(html, /class="action-row results-actions"/);
  assert.match(html, /class="review-summary-metrics results-head-metrics"/);
  assert.match(
    html,
    /class="action-row results-actions">[\s\S]*Preview Timeline[\s\S]*class="results-order-row"[\s\S]*<label class="field field-compact results-order-field">[\s\S]*Order by clip/,
  );
  assert.match(html, /class="icon-button results-expand-button"/);
  assert.doesNotMatch(html, /<section class="timeline-preview" id="timeline-preview-strip">/);
  assert.doesNotMatch(html, /Review the selected shots and export the generated timeline\./);
  assert.doesNotMatch(html, /<span>Order<\/span>/);
  assert.match(html, /Sections<\/span><strong>3 \(3 VLM\)<\/strong>/);
  assert.doesNotMatch(html, /VLM analyzed/);
  assert.doesNotMatch(html, /Runtime/);
  assert.doesNotMatch(html, /Transcript/);
  assert.doesNotMatch(html, /Semantic/);
  assert.doesNotMatch(html, /Cache/);
  assert.doesNotMatch(html, /AI active, transcript partial, semantic degraded, cache active/);
  assert.doesNotMatch(html, /Degraded modes: transcript fallback on 1 asset/);
  assert.doesNotMatch(html, /Intentional skips: AI analysis skipped 3 segments before live VLM/);
  assert.doesNotMatch(html, /Summary/);
});

test("renderResultsStep shows timeline preview frames in timeline order when enabled", () => {
  const appState = buildAppState();
  appState.timelinePreviewOpen = true;
  appState.project = buildProject();

  const html = renderResultsStep(appState);
  const previewIndex = html.indexOf('<section class="timeline-preview" id="timeline-preview-strip">');
  const statusIndex = html.indexOf("Export the current generated timeline to an FCPXML file for DaVinci Resolve.");
  const clipGridIndex = html.indexOf("clip-grid");
  const firstFrameIndex = html.indexOf("segment-1.jpg");
  const secondFrameIndex = html.indexOf("segment-2.jpg");

  assert.ok(previewIndex >= 0);
  assert.ok(statusIndex >= 0);
  assert.ok(previewIndex > statusIndex);
  assert.ok(clipGridIndex > previewIndex);
  assert.ok(firstFrameIndex >= 0);
  assert.ok(secondFrameIndex > firstFrameIndex);
  assert.match(html, /Timeline Preview/);
  assert.match(html, /aria-expanded="true"/);
  assert.match(html, /segment-1\.jpg/);
  assert.match(html, /segment-2\.jpg/);
  assert.match(html, /timeline-preview-duration">4s</);
  assert.doesNotMatch(html, /1\. Opener/);
  assert.doesNotMatch(html, /2\. Bridge/);
});

test("renderResultsStep switches to a flat score-ranked view when requested", () => {
  const appState = buildAppState();
  appState.resultsOrdering = "score";
  appState.project = buildProject();

  appState.project.project.candidate_segments[0]!.prefilter = {
    score: 0.7,
    shortlisted: true,
    filtered_before_vlm: false,
    selection_reason: "Scored well",
  };
  appState.project.project.candidate_segments[1]!.prefilter = {
    score: 0.8,
    shortlisted: true,
    filtered_before_vlm: false,
    selection_reason: "Top score",
  };
  appState.project.project.candidate_segments[2]!.prefilter = {
    score: 0.2,
    shortlisted: true,
    filtered_before_vlm: false,
    selection_reason: "Low score",
  };

  const html = renderResultsStep(appState);
  const rankOneIndex = html.indexOf("Rank 1");
  const segmentTwoIndex = html.indexOf("Segment 2");
  const segmentOneIndex = html.indexOf("Segment 1");

  assert.match(html, /<select data-action="set-results-order"/);
  assert.match(html, /<option value="score" selected>Order by score<\/option>/);
  assert.match(html, /ranked-segment-list/);
  assert.match(html, /Overall 80/);
  assert.match(html, /Clip A · A001/);
  assert.match(
    html,
    /class="results-order-row"[\s\S]*data-action="toggle-all-clips"[\s\S]*class="icon-button results-expand-button"[\s\S]*disabled/,
  );
  assert.ok(rankOneIndex >= 0);
  assert.ok(segmentTwoIndex > rankOneIndex);
  assert.ok(segmentOneIndex > segmentTwoIndex);
});
