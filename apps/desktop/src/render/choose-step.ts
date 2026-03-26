import type { AppState } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";

export function renderChooseStep(appState: AppState) {
  const canContinue = Boolean(appState.mediaDir.trim());
  const videoCountPill = canContinue
    ? `<span class="pill header-pill">videos: ${escapeHtml(appState.mediaSummary ? String(appState.mediaSummary.video_count) : "unknown")}</span>`
    : "";

  return `
    <section class="card view-card">
      <div class="view-head">
        <div>
          <p class="eyebrow">Step 1</p>
          <h2>Choose folder</h2>
          <p class="muted">Pick the footage folder you want the analyzer to process.</p>
        </div>
        ${videoCountPill}
      </div>

      <p class="status ${appState.mediaDir ? "ok" : "warn"}">
        ${escapeHtml(appState.mediaDir || "No media folder selected yet.")}
      </p>

      ${appState.mediaSummaryError ? `<p class="status warn">${escapeHtml(appState.mediaSummaryError)}</p>` : ""}

      <div class="action-row">
        <button data-action="pick-media" class="button secondary">Choose media folder</button>
        <button data-action="go-process" class="button" ${!canContinue ? "disabled" : ""}>Continue to processing</button>
      </div>
    </section>
  `;
}
