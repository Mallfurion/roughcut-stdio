import type { ClipView } from "../../app/types.ts";
import { escapeHtml } from "../../lib/html.ts";
import { renderSegmentCard } from "./segment-card.ts";

export function renderClipCard(
  view: ClipView,
  expandedClipIds: string[],
  expandedDetailPanelIds: string[],
  allowOverrides: boolean,
  reviewBusy: boolean,
) {
  const expanded = expandedClipIds.includes(view.asset.id);
  const dedupCount = view.segments.filter(({ segment }) => segment.prefilter?.deduplicated).length;
  const activeCount = view.segments.length - dedupCount;

  return `
    <article class="clip-card">
      <button class="clip-toggle" data-action="toggle-clip" data-clip-id="${escapeHtml(view.asset.id)}" aria-expanded="${expanded ? "true" : "false"}">
        <div class="clip-head">
          <div class="clip-title-row">
            <h3>${escapeHtml(view.asset.name)}</h3>
            <span class="clip-title-separator" aria-hidden="true">·</span>
            <p class="muted">${escapeHtml(view.asset.interchange_reel_name)}</p>
          </div>
          <div class="clip-toggle-meta">
            <span class="pill">${view.segments.length} sections</span>
            ${dedupCount > 0 ? `<span class="pill pill-dedup-info">${activeCount} active, ${dedupCount} dup</span>` : ""}
            <span class="clip-chevron">${expanded ? "−" : "+"}</span>
          </div>
        </div>
      </button>
      ${
        expanded
          ? `
      <div class="section-list">
        ${view.segments
          .map((segmentView) => renderSegmentCard(segmentView, view.asset, expandedDetailPanelIds, { allowOverrides, reviewBusy }))
          .join("")}
      </div>`
          : ""
      }
    </article>
  `;
}
