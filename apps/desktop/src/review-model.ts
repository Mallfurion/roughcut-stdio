export type ReviewState = {
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

export type ReviewSegment = {
  start_sec: number;
  end_sec: number;
  prefilter?: {
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
  evidence_bundle?: {
    keyframe_timestamps_sec: number[];
    context_window_start_sec: number;
    context_window_end_sec: number;
  };
  ai_understanding?: {
    provider: string;
    keep_label: string;
    confidence: number;
    summary: string;
    rationale: string;
  };
  review_state?: ReviewState;
};

export type ReviewRecommendation = {
  is_best_take: boolean;
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

export type SegmentReviewModel = {
  outcome: string;
  outcomeLabel: string;
  outcomeClassName: string;
  rankLabel: string;
  scoreGapLabel: string;
  decisionSummary: string;
  analysisPathSummary: string;
  scoreValues: {
    total: string;
    technical: string;
    semantic: string;
    story: string;
  };
  driverSummary: string;
  provenance: {
    boundaryLabel: string;
    boundaryConfidence: string;
    lineageSummary: string;
    semanticSummary: string;
    semanticBadge: string;
  };
};

export function buildSegmentReviewModel(
  segment: ReviewSegment,
  recommendation?: ReviewRecommendation,
): SegmentReviewModel {
  const outcome = recommendation?.outcome ?? (recommendation?.is_best_take ? "best" : "backup");
  const scoreGap = Math.max(0, recommendation?.score_gap_to_winner ?? 0);
  const rank = recommendation?.within_asset_rank ?? 0;
  const scoreDrivers = recommendation?.score_driver_labels ?? [];
  const limitingFactors = recommendation?.limiting_factor_labels ?? [];

  return {
    outcome,
    outcomeLabel: outcomeLabel(outcome),
    outcomeClassName: `section-outcome--${outcome}`,
    rankLabel: rank > 0 ? `#${rank} in clip` : "",
    scoreGapLabel: scoreGap > 0 ? `${Math.round(scoreGap * 100)} pts behind winner` : "",
    decisionSummary: recommendation?.selection_reason || segment.ai_understanding?.rationale || segment.prefilter?.selection_reason || "",
    analysisPathSummary: segment.review_state?.analysis_path_summary || deriveAnalysisPath(segment),
    scoreValues: {
      total: formatScoreValue(recommendation?.score_total),
      technical: formatScoreValue(recommendation?.score_technical),
      semantic: formatScoreValue(recommendation?.score_semantic),
      story: formatScoreValue(recommendation?.score_story),
    },
    driverSummary: limitingFactors.length > 0 ? limitingFactors.join(", ") : scoreDrivers.join(", "),
    provenance: {
      boundaryLabel: segment.review_state?.boundary_strategy_label || "",
      boundaryConfidence: formatBoundaryConfidence(segment.review_state?.boundary_confidence),
      lineageSummary: segment.review_state?.lineage_summary || "",
      semanticSummary: segment.review_state?.semantic_validation_summary || "",
      semanticBadge: semanticValidationBadge(segment.review_state?.semantic_validation_status),
    },
  };
}

export function deriveAnalysisPath(segment: ReviewSegment): string {
  const prefilter = segment.prefilter;
  const ai = segment.ai_understanding;
  const clipScore = prefilter?.metrics_snapshot?.["clip_score"];
  const evidenceKeyframes = segment.evidence_bundle?.keyframe_timestamps_sec.length ?? 0;
  const steps: string[] = [];

  if (prefilter?.shortlisted) {
    steps.push("shortlisted");
  } else {
    steps.push("screened locally only");
  }

  if (typeof clipScore === "number") {
    steps.push(`CLIP ${Math.round(clipScore * 100)}`);
  }
  if (prefilter?.deduplicated) {
    steps.push(`deduped in group ${prefilter.dedup_group_id ?? "?"}`);
  }
  if (prefilter?.clip_gated) {
    steps.push("CLIP gated");
  }
  if (prefilter?.vlm_budget_capped) {
    steps.push("budget capped");
  }
  if (evidenceKeyframes > 0) {
    steps.push(`${evidenceKeyframes} keyframe${evidenceKeyframes === 1 ? "" : "s"}`);
  }
  if (ai?.provider) {
    steps.push(ai.provider === "deterministic" ? "deterministic fallback" : `VLM ${ai.provider}`);
  }

  return steps.join(" -> ");
}

export function formatScoreValue(value?: number): string {
  return `${Math.round((value ?? 0) * 100)}`;
}

function formatBoundaryConfidence(value?: number | null): string {
  if (typeof value !== "number") {
    return "";
  }
  return `${Math.round(value * 100)}% confidence`;
}

function semanticValidationBadge(status?: string): string {
  if (!status) {
    return "";
  }
  if (status === "validated") {
    return "Semantic validated";
  }
  if (status === "fallback") {
    return "Semantic fallback";
  }
  if (status === "skipped") {
    return "Semantic skipped";
  }
  if (status === "not_eligible") {
    return "Semantic not needed";
  }
  return status;
}

function outcomeLabel(outcome: string): string {
  if (outcome === "best") {
    return "Best take";
  }
  if (outcome === "alternate") {
    return "Alternate";
  }
  return "Backup";
}
