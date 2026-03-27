import type { AppState } from "../app/types.ts";
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

  return `
    <section class="card view-card">
      <div class="view-head">
        <div>
          <p class="eyebrow">Step 3</p>
          <h2>View results</h2>
          <p class="muted">Review the selected shots and export the generated timeline.</p>
        </div>
        <div class="action-row">
          <button data-action="export-timeline" class="button" ${appState.exportBusy ? "disabled" : ""}>
            ${appState.exportBusy ? "Exporting..." : "Export to Davinci Resolve Timeline"}
          </button>
        </div>
      </div>

      <p class="status ${appState.exportMessage ? "ok" : ""}">
        ${escapeHtml(appState.exportMessage || "Export the current generated timeline to an FCPXML file for DaVinci Resolve.")}
      </p>

      <div class="review-summary">
        <div class="review-summary-metrics">
          ${renderMetric("Project", project.project.name)}
          ${renderMetric("Clips", String(clipViews.length))}
          ${renderMetric("Sections", String(project.candidate_segments.length))}
          ${renderMetric("VLM analyzed", String(vlmAnalyzedCount))}
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

      ${renderRuntimeReliabilitySummary(analysisSummary)}

      <p class="muted">${escapeHtml(project.timeline.story_summary || "The rough timeline is ready for review.")}</p>

      <div class="clip-grid">
        ${clipViews.map((view) => renderClipCard(view, appState.expandedClipIds)).join("")}
      </div>
    </section>
  `;
}

function renderRuntimeReliabilitySummary(analysisSummary: Record<string, string | number | boolean | string[]>) {
  const overallMode = String(analysisSummary.runtime_reliability_mode ?? "").trim();
  const summary = String(analysisSummary.runtime_reliability_summary ?? "").trim();
  if (!overallMode && !summary) {
    return "";
  }

  const aiMode = String(analysisSummary.ai_runtime_mode ?? "unknown");
  const transcriptMode = String(analysisSummary.transcript_runtime_mode ?? "unknown");
  const semanticMode = String(analysisSummary.semantic_boundary_runtime_mode ?? "unknown");
  const cacheMode = String(analysisSummary.cache_runtime_mode ?? "unknown");
  const degradedReasons = Array.isArray(analysisSummary.runtime_degraded_reasons)
    ? analysisSummary.runtime_degraded_reasons.map((value) => String(value)).filter(Boolean)
    : [];
  const intentionalSkipReasons = Array.isArray(analysisSummary.runtime_intentional_skip_reasons)
    ? analysisSummary.runtime_intentional_skip_reasons.map((value) => String(value)).filter(Boolean)
    : [];

  return `
    <div class="review-summary">
      <div class="review-summary-metrics">
        ${renderMetric("Runtime", overallMode || "unknown")}
        ${renderMetric("AI", aiMode)}
        ${renderMetric("Transcript", transcriptMode)}
        ${renderMetric("Semantic", semanticMode)}
        ${renderMetric("Cache", cacheMode)}
      </div>
    </div>
    ${summary ? `<p class="muted">${escapeHtml(summary)}</p>` : ""}
    ${
      degradedReasons.length > 0
        ? `<p class="muted">Degraded modes: ${escapeHtml(degradedReasons.join("; "))}</p>`
        : ""
    }
    ${
      intentionalSkipReasons.length > 0
        ? `<p class="muted">Intentional skips: ${escapeHtml(intentionalSkipReasons.join("; "))}</p>`
        : ""
    }
  `;
}
