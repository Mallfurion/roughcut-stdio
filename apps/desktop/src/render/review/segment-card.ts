import { buildSegmentReviewModel } from "../../review-model.ts";
import type { Asset, CandidateSegment, TakeRecommendation } from "../../app/types.ts";
import { formatSegmentDuration, formatSegmentRange, formatScore } from "../../lib/format.ts";
import { escapeHtml } from "../../lib/html.ts";
import {
  formatProviderLabel,
  renderAudioMetrics,
  renderOptionalMeta,
  renderScoreBar,
  resolveBlockedBadge,
  resolveSegmentImageSrc,
} from "./helpers.ts";

export function renderSegmentCard(
  view: { segment: CandidateSegment; recommendation?: TakeRecommendation },
  asset: Asset,
) {
  const { segment, recommendation } = view;
  const ai = segment.ai_understanding;
  const score = segment.prefilter?.score ?? 0;
  const clipScore = segment.prefilter?.metrics_snapshot?.["clip_score"];
  const vlmText = ai?.summary || segment.description;
  const isDeduplicated = segment.prefilter?.deduplicated ?? false;
  const dedupGroupId = segment.prefilter?.dedup_group_id;
  const review = buildSegmentReviewModel(segment, recommendation);
  const evidence = segment.evidence_bundle;
  const blockedBadge = resolveBlockedBadge(segment);
  const providerLabel = formatProviderLabel(ai?.provider);
  const imageSrc = resolveSegmentImageSrc(evidence);

  const provenanceFacts = [
    review.provenance.boundaryLabel
      ? `${review.provenance.boundaryLabel}${review.provenance.boundaryConfidence ? ` · ${review.provenance.boundaryConfidence}` : ""}`
      : "",
    review.provenance.semanticBadge,
    review.provenance.lineageSummary,
    review.provenance.semanticSummary,
  ].filter(Boolean);

  const sourceFacts = [`Source ${asset.interchange_reel_name}`, asset.source_path].filter(Boolean);
  const quietFacts = [
    score > 0 ? `Prefilter ${formatScore(score)}` : "",
    clipScore !== undefined ? `CLIP ${formatScore(clipScore)}` : "",
    evidence ? `${evidence.keyframe_timestamps_sec.length} keyframe${evidence.keyframe_timestamps_sec.length === 1 ? "" : "s"}` : "",
    evidence ? `Context ${formatSegmentRange(evidence.context_window_start_sec, evidence.context_window_end_sec)}` : "",
    typeof ai?.confidence === "number" ? `Confidence ${Math.round(ai.confidence * 100)}%` : "",
    ai?.keep_label && ai.keep_label !== "n/a" ? `VLM ${ai.keep_label}` : "",
    !isDeduplicated && dedupGroupId !== undefined ? `Dedup keeper G${dedupGroupId}` : "",
  ].filter(Boolean);
  const tonalMeta = [ai?.shot_type, ai?.camera_motion, ai?.mood].filter(Boolean);

  return `
    <article class="section-card ${review.outcomeClassName}${isDeduplicated ? " section-card--deduplicated" : ""}">
      <div class="section-head section-head--compact">
        <div class="pill-row pill-row--primary">
          <span class="pill section-pill">${escapeHtml(formatSegmentRange(segment.start_sec, segment.end_sec))}</span>
          <span class="pill section-pill">${escapeHtml(formatSegmentDuration(segment.start_sec, segment.end_sec))}</span>
          <span class="pill section-pill section-outcome-pill section-outcome-pill--${escapeHtml(review.outcome)}">${escapeHtml(review.outcomeLabel)}</span>
          ${providerLabel ? `<span class="pill section-pill">${escapeHtml(providerLabel)}</span>` : ""}
          ${blockedBadge ? `<span class="pill section-pill ${blockedBadge.className}">${escapeHtml(blockedBadge.label)}</span>` : ""}
        </div>
      </div>
      ${
        imageSrc
          ? `
      <div class="segment-visual">
        <img class="segment-visual-image" src="${escapeHtml(imageSrc)}" alt="${escapeHtml(vlmText || "Segment visual summary")}" />
      </div>`
          : ""
      }
      <p class="section-summary section-summary--hero">${escapeHtml(vlmText)}</p>
      <div class="score-panel">
        <div class="score-hero">
          <span class="score-hero-label">Overall score</span>
          <strong class="score-hero-value">${escapeHtml(review.scoreValues.total)}</strong>
          ${review.rankLabel ? `<span class="score-hero-rank">${escapeHtml(review.rankLabel)}</span>` : ""}
          ${review.scoreGapLabel ? `<span class="score-hero-gap">${escapeHtml(review.scoreGapLabel)}</span>` : ""}
        </div>
        <div class="score-bars">
          ${renderScoreBar("Technical", review.scoreValues.technical)}
          ${renderScoreBar("Semantic", review.scoreValues.semantic)}
          ${renderScoreBar("Story", review.scoreValues.story)}
        </div>
      </div>
      ${
        quietFacts.length > 0
          ? `<div class="meta-list section-facts">${quietFacts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div>`
          : ""
      }
      ${
        provenanceFacts.length > 0
          ? `
      <section class="section-provenance">
        <div class="section-provenance-head">
          <span class="eyebrow section-provenance-eyebrow">Provenance</span>
        </div>
        <div class="section-provenance-list">
          ${provenanceFacts.map((fact) => `<p class="section-provenance-item">${escapeHtml(fact)}</p>`).join("")}
        </div>
        <div class="meta-list section-source-facts">
          ${sourceFacts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}
        </div>
      </section>`
          : ""
      }
      ${review.analysisPathSummary ? `<p class="muted section-analysis-path">${escapeHtml(review.analysisPathSummary)}</p>` : ""}
      <div class="meta-list section-meta">
        ${tonalMeta.map(renderOptionalMeta).join("")}
        ${renderAudioMetrics(segment.prefilter?.metrics_snapshot ?? {})}
      </div>
    </article>
  `;
}
