import test from "node:test";
import assert from "node:assert/strict";

import { resolveClipViews } from "./view-models.ts";
import type { TimelineProject } from "../app/types.ts";

test("resolveClipViews groups segments by asset and sorts them by start time", () => {
  const project: TimelineProject = {
    project: {
      name: "Demo",
      story_prompt: "Prompt",
      status: "ready",
    },
    assets: [
      {
        id: "asset-1",
        name: "Clip A",
        source_path: "/tmp/a.mov",
        has_speech: true,
        interchange_reel_name: "A001",
      },
      {
        id: "asset-2",
        name: "Clip B",
        source_path: "/tmp/b.mov",
        has_speech: false,
        interchange_reel_name: "B001",
      },
    ],
    candidate_segments: [
      {
        id: "seg-2",
        asset_id: "asset-1",
        start_sec: 7,
        end_sec: 9,
        analysis_mode: "visual",
        description: "Later",
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
      {
        id: "seg-1",
        asset_id: "asset-1",
        start_sec: 2,
        end_sec: 4,
        analysis_mode: "visual",
        description: "Earlier",
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
    ],
    take_recommendations: [
      {
        id: "take-1",
        candidate_segment_id: "seg-1",
        title: "Winner",
        is_best_take: true,
        selection_reason: "Best score.",
        score_total: 0.8,
      },
    ],
    timeline: {
      id: "timeline-1",
      version: 1,
      story_summary: "Summary",
      items: [
        {
          id: "timeline-item-1",
          take_recommendation_id: "take-1",
          trim_in_sec: 0,
          trim_out_sec: 4,
          label: "Opener",
          notes: "Open strong",
          source_asset_path: "/tmp/a.mov",
          source_reel: "A001",
          sequence_group: "setup",
          sequence_role: "opener",
          sequence_score: 0.84,
          sequence_rationale: ["Starts on a visual anchor."],
        },
      ],
    },
  };

  const views = resolveClipViews(project);

  assert.equal(views.length, 1);
  assert.equal(views[0]?.asset.id, "asset-1");
  assert.deepEqual(
    views[0]?.segments.map(({ segment }) => segment.id),
    ["seg-1", "seg-2"],
  );
  assert.equal(views[0]?.segments[0]?.recommendation?.id, "take-1");
  assert.equal(views[0]?.segments[0]?.timelineItem?.sequence_group, "setup");
});
