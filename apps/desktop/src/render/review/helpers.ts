import { convertFileSrc } from "@tauri-apps/api/core";

import type { BlockedBadge, CandidateSegment, SegmentEvidence } from "../../app/types.ts";
import { formatScore } from "../../lib/format.ts";
import { escapeHtml } from "../../lib/html.ts";

export function renderScoreBar(label: string, value: string) {
  const numericValue = Math.max(0, Math.min(100, Number(value) || 0));
  return `
    <div class="score-bar">
      <div class="score-bar-head">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
      <div class="score-bar-track">
        <span class="score-bar-fill" style="width: ${numericValue}%"></span>
      </div>
    </div>
  `;
}

export function renderOptionalMeta(value?: string) {
  if (!value) {
    return "";
  }
  return `<span>${escapeHtml(value)}</span>`;
}

export function renderAudioMetrics(metrics: Record<string, number> | undefined) {
  const audioEnergy = metrics?.audio_energy ?? 0;
  const speechRatio = metrics?.speech_ratio ?? 0;

  if (audioEnergy === 0 && speechRatio === 0) {
    return `<span class="pill section-pill audio-pill audio-pill--silent">🔇 Silent</span>`;
  }

  const audioEnergyPercent = Math.round(audioEnergy * 100);
  const speechRatioPercent = Math.round(speechRatio * 100);
  const speechClassName = speechRatio >= 0.5 ? "audio-pill--speech-strong" : "";

  return [
    `<span class="pill section-pill audio-pill">🔊 Energy ${audioEnergyPercent}%</span>`,
    `<span class="pill section-pill audio-pill ${speechClassName}">🎤 Speech ${speechRatioPercent}%</span>`,
  ].join("");
}

export function resolveBlockedBadge(segment: CandidateSegment): BlockedBadge | null {
  const isDeduplicated = segment.prefilter?.deduplicated ?? false;
  const clipGated = segment.prefilter?.clip_gated ?? false;
  const vlmBudgetCapped = segment.prefilter?.vlm_budget_capped ?? false;

  if (isDeduplicated) {
    return { label: "Duplicate", className: "pill-dedup" };
  }
  if (clipGated) {
    return { label: "CLIP gated", className: "pill-warn" };
  }
  if (vlmBudgetCapped) {
    return { label: "Budget capped", className: "pill-accent" };
  }
  return null;
}

export function formatProviderLabel(provider?: string) {
  if (!provider || provider === "deterministic") {
    return "";
  }
  if (provider === "mlx-vlm-local") {
    return "MLX VLM";
  }
  if (provider === "lmstudio") {
    return "LM Studio";
  }
  return provider;
}

export function resolveSegmentImageSrc(evidence?: SegmentEvidence) {
  if (!evidence) {
    return "";
  }
  const sourcePath = evidence.contact_sheet_path || evidence.keyframe_paths[0] || "";
  if (!sourcePath) {
    return "";
  }
  return convertFileSrc(sourcePath);
}

export function buildQuietFacts(segment: CandidateSegment, confidence?: number) {
  const score = segment.prefilter?.score ?? 0;
  const clipScore = segment.prefilter?.metrics_snapshot?.["clip_score"];
  const evidence = segment.evidence_bundle;
  const ai = segment.ai_understanding;
  const isDedupKeeper = !(segment.prefilter?.deduplicated ?? false) && segment.prefilter?.dedup_group_id !== undefined;

  return [
    score > 0 ? `Prefilter ${formatScore(score)}` : "",
    clipScore !== undefined ? `CLIP ${formatScore(clipScore)}` : "",
    evidence ? `${evidence.keyframe_timestamps_sec.length} keyframe${evidence.keyframe_timestamps_sec.length === 1 ? "" : "s"}` : "",
    evidence ? `Context ${segment.evidence_bundle ? `${segment.evidence_bundle.context_window_start_sec.toFixed(2)}s - ${segment.evidence_bundle.context_window_end_sec.toFixed(2)}s` : ""}` : "",
    typeof confidence === "number" ? `Confidence ${Math.round(confidence * 100)}%` : "",
    ai?.keep_label && ai.keep_label !== "n/a" ? `VLM ${ai.keep_label}` : "",
    isDedupKeeper ? `Dedup keeper G${segment.prefilter?.dedup_group_id}` : "",
  ].filter(Boolean);
}
