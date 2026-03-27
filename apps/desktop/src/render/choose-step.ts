import type { AppState } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";

export function renderChooseStep(appState: AppState) {
  const runtimeBlocked =
    !appState.runtimeCheck?.bundled_runtime_ready || Boolean(appState.runtimeCheck?.bootstrap_required);
  const canContinue = Boolean(appState.mediaDir.trim());
  const videoCountPill = canContinue
    ? `<span class="pill header-pill">videos: ${escapeHtml(appState.mediaSummary ? String(appState.mediaSummary.video_count) : "unknown")}</span>`
    : "";
  const showBootstrapCard =
    Boolean(appState.runtimeCheck) &&
    (!appState.runtimeCheck!.bundled_runtime_ready || appState.runtimeCheck!.bootstrap_required);

  if (showBootstrapCard) {
    const runtime = appState.runtimeCheck!;
    const defaultAssets = runtime.default_model_assets.length
      ? `<div><p class="muted">Default packaged assets</p><ul class="runtime-list">${runtime.default_model_assets
          .map((asset) => `<li>${escapeHtml(asset)}</li>`)
          .join("")}</ul></div>`
      : "";
    const providerAssets = runtime.provider_model_assets.length
      ? `<div><p class="muted">Provider-specific assets</p><ul class="runtime-list">${runtime.provider_model_assets
          .map((asset) => `<li>${escapeHtml(asset)}</li>`)
          .join("")}</ul></div>`
      : "";
    const missingAssets = runtime.missing_model_assets.length
      ? `<div><p class="muted">Missing for the current workflow</p><ul class="runtime-list">${runtime.missing_model_assets
          .map((asset) => `<li>${escapeHtml(asset)}</li>`)
          .join("")}</ul></div>`
      : "";
    const actionLabel = runtime.bundled_runtime_ready ? "Download required models" : "Prepare runtime";
    const statusTone = runtime.bundled_runtime_ready ? "warn" : "error";
    const fallbackHint = runtime.fallback_actions.length
      ? `<p class="muted">Fallback is available if you want to continue without these assets.</p>`
      : "";

    return `
      <section class="card view-card">
        <div class="view-head">
          <div>
            <p class="eyebrow">Startup</p>
            <h2>Prepare local runtime</h2>
            <p class="muted">This packaged build needs local runtime assets before the full workflow can start.</p>
          </div>
          <span class="pill header-pill">${escapeHtml(runtime.runtime_backend)}</span>
        </div>

        <p class="status ${statusTone}">
          ${escapeHtml(runtime.detail || runtime.runtime_summary || "Runtime preparation is required.")}
        </p>

        ${defaultAssets}
        ${providerAssets}
        ${missingAssets}
        ${fallbackHint}
        ${appState.runtimeMessage ? `<p class="status ${appState.runtimeCheck?.runtime_ready ? "ok" : "warn"}">${escapeHtml(appState.runtimeMessage)}</p>` : ""}

        <div class="summary-grid">
          <div class="metric"><span>Bundled runtime</span><strong>${runtime.bundled_runtime_ready ? "Ready" : "Missing"}</strong></div>
          <div class="metric"><span>Model assets</span><strong>${runtime.model_assets_ready ? "Ready" : "Missing"}</strong></div>
          <div class="metric"><span>Transcript</span><strong>${escapeHtml(runtime.transcript_runtime_mode || "unknown")}</strong></div>
        </div>

        <div class="action-row">
          <button data-action="prepare-runtime" class="button" ${appState.runtimeBusy ? "disabled" : ""}>
            ${appState.runtimeBusy ? "Preparing..." : actionLabel}
          </button>
          <button data-action="refresh-runtime" class="button secondary" ${appState.runtimeBusy ? "disabled" : ""}>Re-check runtime</button>
          ${
            runtime.fallback_actions.length
              ? `<button data-action="apply-runtime-fallback" class="button secondary" ${appState.runtimeBusy ? "disabled" : ""}>Use fallback settings</button>`
              : ""
          }
        </div>
      </section>
    `;
  }

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
      ${runtimeBlocked ? `<p class="status warn">Runtime preparation is still required before processing can begin.</p>` : ""}

      <div class="action-row">
        <button data-action="pick-media" class="button secondary">Choose media folder</button>
        <button data-action="go-process" class="button" ${!canContinue ? "disabled" : ""}>Continue to processing</button>
      </div>
    </section>
  `;
}
