import { buildSegmentReviewModel } from "../../review-model.ts";
import type { Asset, SegmentView } from "../../app/types.ts";
import { formatSegmentDuration, formatSegmentRange, formatScore } from "../../lib/format.ts";
import { escapeHtml } from "../../lib/html.ts";
import { formatProviderLabel, renderAudioMetrics, renderOptionalMeta, renderScoreBar, resolveBlockedBadge, resolveSegmentImageSrc } from "./helpers.ts";

export function renderSegmentCard(
  view: SegmentView,
  asset: Asset,
  expandedDetailPanelIds: string[],
  options: { allowOverrides: boolean; reviewBusy: boolean; sourceLabel?: string; showImage?: boolean; compact?: boolean } = {
    allowOverrides: false,
    reviewBusy: false,
    showImage: true,
    compact: false,
  }
) {
  const { segment, recommendation, timelineItem } = view;
  const compact = options.compact === true;
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
    review.provenance.boundaryLabel ? `${review.provenance.boundaryLabel}${review.provenance.boundaryConfidence ? ` · ${review.provenance.boundaryConfidence}` : ""}` : "",
    review.provenance.semanticBadge,
    review.provenance.lineageSummary,
    review.provenance.semanticSummary
  ].filter(Boolean);

  const sourceFacts = [`Source ${asset.interchange_reel_name}`, asset.source_path].filter(Boolean);
  const sequenceFacts = [
    timelineItem?.sequence_group ? `Group ${timelineItem.sequence_group}` : "",
    timelineItem?.sequence_role ? `Role ${timelineItem.sequence_role}` : "",
    typeof timelineItem?.sequence_score === "number" ? `Sequence ${formatScore(timelineItem.sequence_score)}` : ""
  ].filter(Boolean);
  const canSetBestTake = options.allowOverrides && Boolean(recommendation) && !recommendation?.is_best_take;
  const canClearBestTake = options.allowOverrides && Boolean(recommendation?.is_best_take && !recommendation?.editor_override);
  const canClearBestTakeOverride = options.allowOverrides && Boolean(recommendation?.is_best_take && recommendation?.editor_override);
  const detailPanels: string[] = [];
  const sequencePanelId = `${segment.id}:sequence`;
  const provenancePanelId = `${segment.id}:provenance`;
  const quietFacts = [
    recommendation?.editor_override && recommendation.is_best_take ? "Editor override" : "",
    recommendation?.editor_cleared ? "Cleared from timeline" : "",
    recommendation?.baseline_is_best_take && !recommendation.is_best_take ? "Analyzer pick" : "",
    score > 0 ? `Prefilter ${formatScore(score)}` : "",
    clipScore !== undefined ? `CLIP ${formatScore(clipScore)}` : "",
    evidence ? `${evidence.keyframe_timestamps_sec.length} keyframe${evidence.keyframe_timestamps_sec.length === 1 ? "" : "s"}` : "",
    evidence ? `Context ${formatSegmentRange(evidence.context_window_start_sec, evidence.context_window_end_sec)}` : "",
    typeof ai?.confidence === "number" ? `Confidence ${Math.round(ai.confidence * 100)}%` : "",
    ai?.keep_label && ai.keep_label !== "n/a" ? `VLM ${ai.keep_label}` : "",
    !isDeduplicated && dedupGroupId !== undefined ? `Dedup keeper G${dedupGroupId}` : ""
  ].filter(Boolean);
  const tonalMeta = [ai?.shot_type, ai?.camera_motion, ai?.mood].filter(Boolean);

  if (!compact && timelineItem?.sequence_rationale?.length) {
    detailPanels.push(
      renderDetailPanel({
        title: "Sequence",
        panelId: sequencePanelId,
        expanded: expandedDetailPanelIds.includes(sequencePanelId),
        content: `
          ${sequenceFacts.length > 0 ? `<div class="meta-list section-source-facts">${sequenceFacts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div>` : ""}
          <div class="section-provenance-list">
          ${timelineItem.sequence_rationale.map((fact) => `<p class="section-provenance-item">${escapeHtml(fact)}</p>`).join("")}
          </div>`
      }),
    );
  }

  if (!compact && provenanceFacts.length > 0) {
    detailPanels.push(
      renderDetailPanel({
        title: "Provenance",
        panelId: provenancePanelId,
        expanded: expandedDetailPanelIds.includes(provenancePanelId),
        content: `<div class="section-provenance-list">
          ${provenanceFacts.map((fact) => `<p class="section-provenance-item">${escapeHtml(fact)}</p>`).join("")}
        </div>
        <div class="meta-list section-source-facts">
          ${sourceFacts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}
        </div>`
      }),
    );
  }

  return `
    <article class="section-card ${review.outcomeClassName}${isDeduplicated ? " section-card--deduplicated" : ""}${compact ? " section-card--compact" : ""}">
      <div class="section-head section-head--compact">
        <div class="pill-row pill-row--primary">
          <span class="pill section-pill">${escapeHtml(formatSegmentRange(segment.start_sec, segment.end_sec))}</span>
          <span class="pill section-pill">${escapeHtml(formatSegmentDuration(segment.start_sec, segment.end_sec))}</span>
          <span class="pill section-pill section-outcome-pill section-outcome-pill--${escapeHtml(review.outcome)}">${escapeHtml(review.outcomeLabel)}</span>
          ${options.sourceLabel ? `<span class="pill section-pill">${escapeHtml(options.sourceLabel)}</span>` : ""}
          ${providerLabel ? `<span class="pill section-pill">${escapeHtml(providerLabel)}</span>` : ""}
          ${blockedBadge ? `<span class="pill section-pill ${blockedBadge.className}">${escapeHtml(blockedBadge.label)}</span>` : ""}
        </div>
        ${
          canSetBestTake || canClearBestTake || canClearBestTakeOverride
            ? `
        <div class="action-row section-card-actions">
          ${
            canSetBestTake
              ? `<button
                  data-action="set-best-take"
                  data-asset-id="${escapeHtml(asset.id)}"
                  data-segment-id="${escapeHtml(segment.id)}"
                  class="button"
                  ${options.reviewBusy ? "disabled" : ""}
                >Mark As Best Take</button>`
              : ""
          }
          ${
            canClearBestTake
              ? `<button
                  data-action="clear-best-take"
                  data-asset-id="${escapeHtml(asset.id)}"
                  class="button button-danger-soft"
                  ${options.reviewBusy ? "disabled" : ""}
                >Clear Best Take</button>`
              : ""
          }
          ${
            canClearBestTakeOverride
              ? `<button
                  data-action="clear-best-take-override"
                  data-asset-id="${escapeHtml(asset.id)}"
                  class="button button-warning-soft"
                  ${options.reviewBusy ? "disabled" : ""}
                >Clear Override</button>`
              : ""
          }
        </div>`
            : ""
        }
      </div>
      ${
        !compact && imageSrc && options.showImage !== false
          ? `
      <div class="segment-visual">
        <img class="segment-visual-image" src="${escapeHtml(imageSrc)}" alt="${escapeHtml(vlmText || "Segment visual summary")}" loading="lazy" decoding="async" />
      </div>`
          : ""
      }
      <p class="section-summary${compact ? "" : " section-summary--hero"}">${escapeHtml(vlmText)}</p>
      ${
        compact
          ? `
      <div class="score-hero score-hero--compact">
        <span class="score-hero-label">Overall score</span>
        <strong class="score-hero-value score-hero-value--compact">${escapeHtml(review.scoreValues.total)}</strong>
        ${review.rankLabel ? `<span class="score-hero-rank">${escapeHtml(review.rankLabel)}</span>` : ""}
        ${review.scoreGapLabel ? `<span class="score-hero-gap">${escapeHtml(review.scoreGapLabel)}</span>` : ""}
      </div>`
          : `
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
      </div>`
      }
      ${
        quietFacts.length > 0
          ? `<div class="meta-list section-facts">${(compact ? quietFacts.slice(0, 4) : quietFacts).map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div>`
          : ""
      }
      ${!compact && detailPanels.length > 0 ? `<div class="section-detail-grid${detailPanels.length === 1 ? " section-detail-grid--single" : ""}">${detailPanels.join("")}</div>` : ""}
      ${
        compact
          ? ""
          : `<div class="meta-list section-meta">
        ${tonalMeta.map(renderOptionalMeta).join("")}
        ${renderAudioMetrics(segment.prefilter?.metrics_snapshot ?? {})}
      </div>`
      }
    </article>
  `;
}

function renderDetailPanel(options: { title: string; panelId: string; expanded: boolean; content: string }) {
  return `
    <section class="section-provenance${options.expanded ? "" : " section-provenance--collapsed"}">
      <div class="section-provenance-head">
        <span class="eyebrow section-provenance-eyebrow">${escapeHtml(options.title)}</span>
        <button
          data-action="toggle-detail-panel"
          data-panel-id="${escapeHtml(options.panelId)}"
          class="icon-button section-detail-toggle"
          aria-expanded="${options.expanded ? "true" : "false"}"
          aria-label="${options.expanded ? `Collapse ${options.title}` : `Expand ${options.title}`}"
          title="${options.expanded ? `Collapse ${options.title}` : `Expand ${options.title}`}"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            ${options.expanded ? '<path d="M19 13H5v-2h14v2Z" />' : '<path d="M4 14h6v6h2v-6h6v-2h-6V6h-2v6H4v2Z" />'}
          </svg>
        </button>
      </div>
      ${options.expanded ? options.content : ""}
    </section>
  `;
}
