import test from "node:test";
import assert from "node:assert/strict";

import { renderResultsStep } from "./results-step.ts";
import type { AppState, LoadedProject } from "../app/types.ts";

test("renderResultsStep shows concise runtime reliability summary when analysis summary includes it", () => {
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
    allClipsExpanded: false,
    project: null,
    exportPath: "",
    exportBusy: false,
    exportMessage: "",
  };
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
      assets: [],
      candidate_segments: [],
      take_recommendations: [],
      timeline: {
        id: "timeline-1",
        version: 1,
        story_summary: "Summary",
        items: [],
      },
    },
  };
  appState.project = project;

  const html = renderResultsStep(appState);

  assert.match(html, /Runtime/);
  assert.match(html, /Transcript/);
  assert.match(html, /Degraded modes: transcript fallback on 1 asset/);
  assert.match(html, /Intentional skips: AI analysis skipped 3 segments before live VLM/);
  assert.doesNotMatch(html, /runtime_degraded_reasons/);
});
