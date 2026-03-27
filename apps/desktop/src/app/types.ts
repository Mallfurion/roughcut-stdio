export type Step = "choose" | "process" | "results";
export type AIMode = "fast" | "full";
export type AIProvider = "deterministic" | "lmstudio" | "mlx-vlm-local";
export type TranscriptProvider = "auto" | "disabled" | "faster-whisper";
export type ResultsOrdering = "clip" | "score";

export type ProcessState = {
  running: boolean;
  status: string;
  processed: number;
  total: number;
  current_asset: string;
  elapsed: string;
  eta: string;
  logs: string[];
  output_path?: string | null;
  error?: string | null;
};

export type RuntimeCheck = {
  runtime_backend: string;
  configured_provider: string;
  effective_provider: string;
  model: string;
  revision: string;
  cache_dir: string;
  device: string;
  base_url: string;
  available: boolean;
  detail: string;
  runtime_ready: boolean;
  bundled_runtime_ready: boolean;
  model_assets_ready: boolean;
  bootstrap_required: boolean;
  default_model_assets: string[];
  provider_model_assets: string[];
  missing_model_assets: string[];
  fallback_actions: string[];
  runtime_reliability_mode: string;
  ai_runtime_mode: string;
  transcript_runtime_mode: string;
  semantic_boundary_runtime_mode: string;
  cache_runtime_mode: string;
  transcript_provider_configured: string;
  transcript_provider_effective: string;
  transcript_model_size: string;
  transcript_enabled: boolean;
  transcript_available: boolean;
  transcript_status: string;
  transcript_detail: string;
  degraded: boolean;
  degraded_reasons: string[];
  intentional_skip_reasons: string[];
  runtime_summary: string;
  output: string;
};

export type MediaFolderSummary = {
  path: string;
  video_count: number;
};

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
  audio_energy?: number;
  speech_ratio?: number;
};

export type SegmentEvidence = {
  keyframe_paths: string[];
  keyframe_timestamps_sec: number[];
  context_window_start_sec: number;
  context_window_end_sec: number;
  contact_sheet_path?: string;
};

export type SegmentPrefilter = {
  score: number;
  shortlisted: boolean;
  filtered_before_vlm: boolean;
  selection_reason: string;
  deduplicated?: boolean;
  dedup_group_id?: number;
  clip_gated?: boolean;
  vlm_budget_capped?: boolean;
  metrics_snapshot?: Record<string, number>;
};

export type SegmentUnderstanding = {
  provider: string;
  keep_label: string;
  confidence: number;
  summary: string;
  rationale: string;
  story_roles: string[];
  shot_type: string;
  camera_motion: string;
  mood: string;
  risk_flags: string[];
};

export type SegmentReviewState = {
  shortlisted: boolean;
  filtered_before_vlm: boolean;
  clip_scored: boolean;
  clip_score?: number | null;
  clip_gated?: boolean;
  deduplicated?: boolean;
  dedup_group_id?: number | null;
  vlm_budget_capped?: boolean;
  model_analyzed?: boolean;
  deterministic_fallback?: boolean;
  evidence_keyframe_count?: number;
  analysis_path_summary?: string;
  blocked_reason?: string;
  boundary_strategy_label?: string;
  boundary_confidence?: number | null;
  lineage_summary?: string;
  semantic_validation_status?: string;
  semantic_validation_summary?: string;
};

export type Asset = {
  id: string;
  name: string;
  source_path: string;
  has_proxy?: boolean;
  has_speech: boolean;
  interchange_reel_name: string;
};

export type CandidateSegment = {
  id: string;
  asset_id: string;
  start_sec: number;
  end_sec: number;
  analysis_mode: "speech" | "visual";
  description: string;
  transcript_excerpt: string;
  quality_metrics: QualityMetrics;
  evidence_bundle?: SegmentEvidence;
  prefilter?: SegmentPrefilter;
  ai_understanding?: SegmentUnderstanding;
  review_state?: SegmentReviewState;
};

export type TakeRecommendation = {
  id: string;
  candidate_segment_id: string;
  title: string;
  is_best_take: boolean;
  baseline_is_best_take?: boolean;
  editor_override?: boolean;
  editor_cleared?: boolean;
  selection_reason: string;
  score_technical?: number;
  score_semantic?: number;
  score_story?: number;
  score_total: number;
  outcome?: string;
  within_asset_rank?: number;
  score_gap_to_winner?: number;
  score_driver_labels?: string[];
  limiting_factor_labels?: string[];
};

export type TimelineItem = {
  id: string;
  take_recommendation_id: string;
  trim_in_sec: number;
  trim_out_sec: number;
  label: string;
  notes: string;
  source_asset_path: string;
  source_reel: string;
  sequence_group?: string;
  sequence_role?: string;
  sequence_score?: number;
  sequence_rationale?: string[];
};

export type TimelineProject = {
  project: {
    name: string;
    story_prompt: string;
    status: string;
    analysis_summary?: Record<string, string | number | boolean | string[]>;
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

export type LoadedProject = {
  project: TimelineProject;
  source: "generated" | "sample";
  file_path: string;
};

export type AppSettings = {
  aiProvider: AIProvider;
  projectName: string;
  storyPrompt: string;
  aiMode: AIMode;
  aiTimeoutSec: string;
  aiModel: string;
  aiBaseUrl: string;
  aiModelId: string;
  aiDevice: string;
  aiMaxSegmentsPerAsset: string;
  aiMaxKeyframes: string;
  aiKeyframeMaxWidth: string;
  aiConcurrency: string;
  aiCacheEnabled: boolean;
  transcriptProvider: TranscriptProvider;
  transcriptModelSize: string;
  audioEnabled: boolean;
  deduplicationEnabled: boolean;
  dedupThreshold: string;
  clipEnabled: boolean;
  clipMinScore: string;
  vlmBudgetPct: string;
  segmentBoundaryRefinementEnabled: boolean;
  segmentLegacyFallbackEnabled: boolean;
  segmentSemanticValidationEnabled: boolean;
  segmentSemanticAmbiguityThreshold: string;
  segmentSemanticValidationBudgetPct: string;
  segmentSemanticValidationMaxSegments: string;
  segmentSemanticMaxAdjustmentSec: string;
};

export type AppState = {
  currentStep: Step;
  mediaDir: string;
  aiMode: AIMode;
  settings: AppSettings | null;
  settingsDraft: AppSettings | null;
  settingsOpen: boolean;
  settingsBusy: boolean;
  settingsMessage: string;
  mediaSummary: MediaFolderSummary | null;
  mediaSummaryError: string;
  runtimeCheck: RuntimeCheck | null;
  runtimeBusy: boolean;
  runtimeMessage: string;
  process: ProcessState;
  processLogsExpanded: boolean;
  expandedClipIds: string[];
  allClipsExpanded: boolean;
  project: LoadedProject | null;
  reviewBusy: boolean;
  exportPath: string;
  exportBusy: boolean;
  exportMessage: string;
  timelinePreviewOpen: boolean;
  resultsOrdering: ResultsOrdering;
};

export type SegmentView = {
  asset: Asset;
  segment: CandidateSegment;
  recommendation?: TakeRecommendation;
  timelineItem?: TimelineItem;
  orderingScore: number;
};

export type ClipView = {
  asset: Asset;
  segments: SegmentView[];
};

export type BlockedBadge = {
  label: string;
  className: string;
};
