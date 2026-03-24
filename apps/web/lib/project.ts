import { readFile } from "node:fs/promises";
import { access } from "node:fs/promises";
import path from "node:path";

export type QualityMetrics = {
  sharpness: number;
  stability: number;
  visual_novelty: number;
  subject_clarity: number;
  motion_energy: number;
  duration_fit: number;
  speech_presence: number;
  hook_strength: number;
  story_alignment: number;
};

export type SegmentEvidence = {
  media_path: string;
  transcript_excerpt: string;
  story_prompt: string;
  analysis_mode: "speech" | "visual";
  keyframe_timestamps_sec: number[];
  keyframe_paths: string[];
  contact_sheet_path?: string;
  context_window_start_sec: number;
  context_window_end_sec: number;
  metrics_snapshot: QualityMetrics;
};

export type SegmentUnderstanding = {
  provider: string;
  provider_model: string;
  schema_version: string;
  summary: string;
  subjects: string[];
  actions: string[];
  shot_type: string;
  camera_motion: string;
  mood: string;
  story_roles: string[];
  quality_findings: string[];
  keep_label: string;
  confidence: number;
  rationale: string;
  risk_flags: string[];
  visual_distinctiveness: number;
  clarity: number;
  story_relevance: number;
};

export type Asset = {
  id: string;
  name: string;
  source_path: string;
  proxy_path: string;
  duration_sec: number;
  fps: number;
  width: number;
  height: number;
  has_speech: boolean;
  interchange_reel_name: string;
  source_timecode?: string;
  has_proxy?: boolean;
  proxy_match_confidence?: number;
  proxy_match_reason?: string;
};

export type CandidateSegment = {
  id: string;
  asset_id: string;
  start_sec: number;
  end_sec: number;
  analysis_mode: "speech" | "visual";
  transcript_excerpt: string;
  description: string;
  quality_metrics: QualityMetrics;
  evidence_bundle?: SegmentEvidence;
  ai_understanding?: SegmentUnderstanding;
};

export type TakeRecommendation = {
  id: string;
  candidate_segment_id: string;
  title: string;
  is_best_take: boolean;
  selection_reason: string;
  score_technical: number;
  score_semantic: number;
  score_story: number;
  score_total: number;
};

export type TimelineItem = {
  id: string;
  take_recommendation_id: string;
  order_index: number;
  trim_in_sec: number;
  trim_out_sec: number;
  label: string;
  notes: string;
  source_asset_path: string;
  source_reel: string;
};

export type TimelineProject = {
  project: {
    id: string;
    name: string;
    story_prompt: string;
    status: string;
    media_roots?: string[];
    analysis_summary?: {
      prefilter_sample_count?: number;
      candidate_segment_count?: number;
      prefilter_shortlisted_count?: number;
      vlm_target_count?: number;
      filtered_before_vlm_count?: number;
    };
  };
  assets: Asset[];
  candidate_segments: CandidateSegment[];
  take_recommendations: TakeRecommendation[];
  timeline: {
    id: string;
    version: number;
    story_summary: string;
    items: TimelineItem[];
  };
};

export type TakeView = {
  take: TakeRecommendation;
  segment: CandidateSegment;
  asset: Asset;
};

export type LoadedProject = {
  project: TimelineProject;
  source: "generated" | "sample";
  filePath: string;
};

export async function loadActiveProject(): Promise<LoadedProject> {
  const generatedPath = path.resolve(process.cwd(), "../../generated/project.json");
  const samplePath = path.resolve(process.cwd(), "../../fixtures/sample-project.json");

  if (await fileExists(generatedPath)) {
    const source = await readFile(generatedPath, "utf8");
    return {
      project: JSON.parse(source) as TimelineProject,
      source: "generated",
      filePath: generatedPath,
    };
  }

  const source = await readFile(samplePath, "utf8");
  return {
    project: JSON.parse(source) as TimelineProject,
    source: "sample",
    filePath: samplePath,
  };
}

export function resolveTakeViews(project: TimelineProject): TakeView[] {
  const segmentById = new Map(project.candidate_segments.map((segment) => [segment.id, segment]));
  const assetById = new Map(project.assets.map((asset) => [asset.id, asset]));

  return project.take_recommendations
    .filter((take) => take.is_best_take)
    .map((take) => {
      const segment = segmentById.get(take.candidate_segment_id);

      if (!segment) {
        throw new Error(`Missing segment for take ${take.id}`);
      }

      const asset = assetById.get(segment.asset_id);

      if (!asset) {
        throw new Error(`Missing asset for segment ${segment.id}`);
      }

      return {
        take,
        segment,
        asset
      };
    });
}

export function computeScoreLabel(
  take: TakeRecommendation,
  segment?: CandidateSegment,
): string {
  const total =
    take.score_total ||
    average([take.score_technical, take.score_semantic, take.score_story]) ||
    average(
      segment
        ? [
            segment.quality_metrics.hook_strength,
            segment.quality_metrics.story_alignment,
            segment.quality_metrics.duration_fit,
          ]
        : [],
    );

  return `${Math.round(total * 100)} / 100`;
}

export function formatDuration(startSec: number, endSec: number): string {
  const duration = Math.max(0, endSec - startSec);
  return `${duration.toFixed(2)}s`;
}

function average(values: number[]): number {
  const safeValues = values.filter((value) => Number.isFinite(value));

  if (safeValues.length === 0) {
    return 0;
  }

  return safeValues.reduce((sum, value) => sum + value, 0) / safeValues.length;
}

async function fileExists(targetPath: string): Promise<boolean> {
  try {
    await access(targetPath);
    return true;
  } catch {
    return false;
  }
}
