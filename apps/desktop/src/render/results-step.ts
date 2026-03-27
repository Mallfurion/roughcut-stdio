import { convertFileSrc } from "@tauri-apps/api/core";

import type { AppState, TimelineProject } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";
import { renderMetric } from "./shared.ts";
import { resolveClipViews } from "./view-models.ts";
import { renderClipCard } from "./review/clip-list.ts";

export function renderResultsStep(appState: AppState) {
  const project = appState.project?.project;
  if (!project) {
    return `
      <section class="card view-card">
        <div class="view-head">
          <div>
            <p class="eyebrow">Step 3</p>
            <h2>View results</h2>
            <p class="muted">No generated results are currently loaded.</p>
          </div>
        </div>
        <p class="empty-state">Run processing first, then return here to review the shortlisted shots.</p>
      </section>
    `;
  }

  const clipViews = resolveClipViews(project);
  const analysisSummary = project.project.analysis_summary ?? {};
  const vlmAnalyzedCount =
    Number(analysisSummary.ai_live_segment_count ?? 0) + Number(analysisSummary.ai_cached_segment_count ?? 0);
  const sectionsMetricValue = `${project.candidate_segments.length} (${vlmAnalyzedCount} VLM)`;
  const timelinePreviewItems = resolveTimelinePreviewItems(project);

  return `
    <section class="card view-card">
      <div class="view-head">
        <div>
          <p class="eyebrow">Step 3</p>
          <h2>View results</h2>
          <p class="muted">Review the selected shots and export the generated timeline.</p>
        </div>
        <div class="action-row results-actions">
          <button data-action="export-timeline" class="button" ${appState.exportBusy ? "disabled" : ""}>
            ${appState.exportBusy ? "Exporting..." : "Export to Davinci Resolve Timeline"}
          </button>
          <button
            data-action="toggle-timeline-preview"
            class="button secondary"
            aria-expanded="${appState.timelinePreviewOpen ? "true" : "false"}"
            aria-controls="timeline-preview-strip"
          >
            Preview Timeline
          </button>
        </div>
      </div>

      <p class="status ${appState.exportMessage ? "ok" : ""}">
        ${escapeHtml(appState.exportMessage || "Export the current generated timeline to an FCPXML file for DaVinci Resolve.")}
      </p>

      ${
        appState.timelinePreviewOpen
          ? renderTimelinePreview(timelinePreviewItems)
          : ""
      }

      <div class="review-summary">
        <div class="review-summary-metrics">
          ${renderMetric("Project", project.project.name)}
          ${renderMetric("Clips", String(clipViews.length))}
          ${renderMetric("Sections", sectionsMetricValue)}
        </div>
        <button
          data-action="toggle-all-clips"
          class="icon-button"
          title="${appState.allClipsExpanded ? "Collapse all" : "Expand all"}"
          aria-label="${appState.allClipsExpanded ? "Collapse all clips" : "Expand all clips"}"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            ${appState.allClipsExpanded ? '<path d="M19 13H5v-2h14v2Z" />' : '<path d="M4 14h6v6h2v-6h6v-2h-6V6h-2v6H4v2Z" />'}
          </svg>
        </button>
      </div>

      <div class="clip-grid">
        ${clipViews.map((view) => renderClipCard(view, appState.expandedClipIds, appState.project?.source === "generated", appState.reviewBusy)).join("")}
      </div>
    </section>
  `;
}

type TimelinePreviewItem = {
  id: string;
  title: string;
  durationLabel: string;
  imageSrc: string;
};

function resolveTimelinePreviewItems(project: TimelineProject): TimelinePreviewItem[] {
  const recommendationsById = new Map(project.take_recommendations.map((recommendation) => [recommendation.id, recommendation]));
  const segmentsById = new Map(project.candidate_segments.map((segment) => [segment.id, segment]));
  return project.timeline.items.flatMap((item, index) => {
    const recommendation = recommendationsById.get(item.take_recommendation_id);
    if (!recommendation) {
      return [];
    }

    const segment = segmentsById.get(recommendation.candidate_segment_id);
    if (!segment) {
      return [];
    }

    const previewPath = segment.evidence_bundle?.keyframe_paths[0] || segment.evidence_bundle?.contact_sheet_path || "";
    const durationSec = item.trim_out_sec > item.trim_in_sec ? item.trim_out_sec - item.trim_in_sec : segment.end_sec - segment.start_sec;

    return [
      {
        id: item.id,
        title: item.label || segment.description || `Shot ${index + 1}`,
        durationLabel: formatPreviewDuration(durationSec),
        imageSrc: previewPath ? resolvePreviewImageSrc(previewPath) : "",
      },
    ];
  });
}

function renderTimelinePreview(items: TimelinePreviewItem[]) {
  return `
    <section class="timeline-preview" id="timeline-preview-strip">
      <div class="timeline-preview-head">
        <span class="eyebrow">Timeline Preview</span>
      </div>
      ${
        items.length > 0
          ? `
      <div class="timeline-preview-track">
        ${items
          .map(
            (item) => `
          <article class="timeline-preview-shot">
            <div class="timeline-preview-frame${item.imageSrc ? "" : " timeline-preview-frame--empty"}">
              ${
                item.imageSrc
                  ? `<img src="${escapeHtml(item.imageSrc)}" alt="${escapeHtml(item.title)}" />`
                  : `<span>No frame</span>`
              }
              <span class="pill timeline-preview-duration">${escapeHtml(item.durationLabel)}</span>
            </div>
          </article>`,
          )
          .join("")}
      </div>`
          : `<p class="muted timeline-preview-empty">No selected timeline shots are available for preview yet.</p>`
      }
    </section>
  `;
}

function resolvePreviewImageSrc(path: string) {
  if (typeof window === "undefined") {
    return path;
  }
  return convertFileSrc(path);
}

function formatPreviewDuration(durationSec: number) {
  const rounded = Math.round(durationSec * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded}s` : `${rounded.toFixed(1)}s`;
}
