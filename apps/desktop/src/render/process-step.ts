import type { AppState } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";
import { renderMetric } from "./shared.ts";

export function renderProcessStep(appState: AppState, canViewResults: boolean) {
  const runtimeBlocked =
    !appState.runtimeCheck?.bundled_runtime_ready || Boolean(appState.runtimeCheck?.bootstrap_required);
  const processPercent = appState.process.total
    ? Math.max(0, Math.min(100, Math.round((appState.process.processed / appState.process.total) * 100)))
    : 0;

  return `
    <section class="card view-card">
      <div class="view-head">
        <div>
          <p class="eyebrow">Step 2</p>
          <h2>Process videos</h2>
          <p class="muted">Run the analyzer on the selected folder and watch the progress here.</p>
        </div>
        <label class="field field-compact">
          AI mode
          <select data-action="set-ai-mode">
            <option value="fast" ${appState.aiMode === "fast" ? "selected" : ""}>Fast</option>
            <option value="full" ${appState.aiMode === "full" ? "selected" : ""}>Full</option>
          </select>
        </label>
      </div>

      <div class="summary-grid">
        ${renderMetric("Folder", appState.mediaDir || "Missing")}
        ${renderMetric("Videos", appState.mediaSummary ? String(appState.mediaSummary.video_count) : "Unknown")}
        ${renderMetric("AI mode", appState.aiMode)}
      </div>

      ${
        runtimeBlocked
          ? `<p class="status warn">Runtime preparation is required before processing can start. Return to step 1 to prepare the packaged runtime${appState.runtimeCheck?.fallback_actions.length ? " or apply fallback settings" : ""}.</p>`
          : ""
      }

      <div class="progress">
        <div class="progress-bar">
          <span style="width:${processPercent}%"></span>
        </div>
        <div class="progress-meta">
          <strong>${processPercent}%</strong>
          <span>${appState.process.processed}/${appState.process.total || "?"} assets</span>
          <span>${escapeHtml(appState.process.current_asset || "Waiting to start")}</span>
          <span>elapsed ${escapeHtml(appState.process.elapsed)} · eta ${escapeHtml(appState.process.eta)}</span>
        </div>
      </div>

      <div class="action-row">
        <button data-action="start-process" class="button" ${!appState.mediaDir || appState.process.running || runtimeBlocked ? "disabled" : ""}>
          ${appState.process.running ? "Processing..." : "Start process"}
        </button>
        <button data-action="view-results" class="button secondary" ${!canViewResults ? "disabled" : ""}>View results</button>
        <button data-action="toggle-logs" class="button secondary">
          ${appState.processLogsExpanded ? "Hide Logs" : "Show Logs"}
        </button>
      </div>

      ${appState.processLogsExpanded ? `<pre id="process-log" class="log-box log-box-large">${escapeHtml(appState.process.logs.join("\n"))}</pre>` : ""}
    </section>
  `;
}
