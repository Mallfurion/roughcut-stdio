import type { AIProvider, AppState } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";

export function renderSettingsDialog(appState: AppState) {
  if (!appState.settingsOpen || !appState.settingsDraft) {
    return "";
  }

  const draft = appState.settingsDraft;
  const provider = draft.aiProvider;

  return `
    <div class="dialog-backdrop">
      <section class="dialog-card">
        <div class="view-head dialog-head">
          <div>
            <p class="eyebrow">Settings</p>
            <h2>Application settings</h2>
            <p class="muted">Save env-backed defaults for provider selection, prompts, and AI runtime tuning.</p>
          </div>
          <button data-action="close-settings" class="icon-button" title="Close settings" aria-label="Close settings">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6 18 18" />
              <path d="M18 6 6 18" />
            </svg>
          </button>
        </div>

        ${appState.settingsMessage ? `<p class="status ${appState.settingsMessage.startsWith("Saved") ? "ok" : "warn"}">${escapeHtml(appState.settingsMessage)}</p>` : ""}

        <div class="settings-grid">
          <section class="settings-section">
            <h3>General</h3>
            <div class="field-grid">
              <label class="field">
                AI provider
                <select data-settings-field="aiProvider">
                  ${renderProviderOption("deterministic", provider)}
                  ${renderProviderOption("lmstudio", provider)}
                  ${renderProviderOption("mlx-vlm-local", provider)}
                </select>
              </label>
              <label class="field">
                AI mode
                <select data-settings-field="aiMode">
                  <option value="fast" ${draft.aiMode === "fast" ? "selected" : ""}>Fast</option>
                  <option value="full" ${draft.aiMode === "full" ? "selected" : ""}>Full</option>
                </select>
              </label>
              <label class="field">
                Project name
                <input data-settings-field="projectName" type="text" value="${escapeHtml(draft.projectName)}" />
              </label>
              <label class="field">
                Story prompt
                <textarea data-settings-field="storyPrompt" rows="4">${escapeHtml(draft.storyPrompt)}</textarea>
              </label>
            </div>
          </section>

          <section class="settings-section">
            <h3>Provider</h3>
            <div class="field-grid">
              ${
                provider === "lmstudio"
                  ? `
                <label class="field">
                  LM Studio model
                  <input data-settings-field="aiModel" type="text" value="${escapeHtml(draft.aiModel)}" />
                </label>
                <label class="field">
                  LM Studio base URL
                  <input data-settings-field="aiBaseUrl" type="text" value="${escapeHtml(draft.aiBaseUrl)}" />
                </label>`
                  : ""
              }
              ${
                provider === "mlx-vlm-local"
                  ? `
                <label class="field">
                  MLX-VLM model ID
                  <input data-settings-field="aiModelId" type="text" value="${escapeHtml(draft.aiModelId)}" />
                </label>
                <label class="field">
                  MLX-VLM device
                  <select data-settings-field="aiDevice">
                    <option value="auto" ${draft.aiDevice === "auto" ? "selected" : ""}>auto</option>
                    <option value="metal" ${draft.aiDevice === "metal" ? "selected" : ""}>metal</option>
                    <option value="cpu" ${draft.aiDevice === "cpu" ? "selected" : ""}>cpu</option>
                  </select>
                </label>`
                  : ""
              }
              ${provider === "deterministic" ? `<p class="muted">Deterministic mode does not require model-specific configuration.</p>` : ""}
            </div>
          </section>

          <section class="settings-section">
            <h3>Advanced</h3>
            <div class="field-grid settings-grid-advanced">
              <label class="field">
                AI timeout (sec)
                <input data-settings-field="aiTimeoutSec" type="number" min="1" value="${escapeHtml(draft.aiTimeoutSec)}" />
              </label>
              <label class="field">
                Max segments per asset
                <input data-settings-field="aiMaxSegmentsPerAsset" type="number" min="1" value="${escapeHtml(draft.aiMaxSegmentsPerAsset)}" />
              </label>
              <label class="field">
                Max keyframes per segment
                <input data-settings-field="aiMaxKeyframes" type="number" min="1" value="${escapeHtml(draft.aiMaxKeyframes)}" />
              </label>
              <label class="field">
                Keyframe max width
                <input data-settings-field="aiKeyframeMaxWidth" type="number" min="160" value="${escapeHtml(draft.aiKeyframeMaxWidth)}" />
              </label>
              <label class="field">
                AI concurrency
                <input data-settings-field="aiConcurrency" type="number" min="1" value="${escapeHtml(draft.aiConcurrency)}" />
              </label>
              <label class="field">
                Transcript provider
                <select data-settings-field="transcriptProvider">
                  <option value="auto" ${draft.transcriptProvider === "auto" ? "selected" : ""}>auto</option>
                  <option value="faster-whisper" ${draft.transcriptProvider === "faster-whisper" ? "selected" : ""}>faster-whisper</option>
                  <option value="disabled" ${draft.transcriptProvider === "disabled" ? "selected" : ""}>disabled</option>
                </select>
              </label>
              <label class="field">
                Transcript model size
                <input data-settings-field="transcriptModelSize" type="text" value="${escapeHtml(draft.transcriptModelSize)}" />
              </label>
              <label class="field">
                Dedup threshold
                <input data-settings-field="dedupThreshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(draft.dedupThreshold)}" />
              </label>
              <label class="field">
                CLIP min score
                <input data-settings-field="clipMinScore" type="number" min="0" max="1" step="0.01" value="${escapeHtml(draft.clipMinScore)}" />
              </label>
              <label class="field">
                VLM budget %
                <input data-settings-field="vlmBudgetPct" type="number" min="0" max="100" step="1" value="${escapeHtml(draft.vlmBudgetPct)}" />
              </label>
              <label class="field">
                Semantic ambiguity threshold
                <input data-settings-field="segmentSemanticAmbiguityThreshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(draft.segmentSemanticAmbiguityThreshold)}" />
              </label>
              <label class="field">
                Semantic validation budget %
                <input data-settings-field="segmentSemanticValidationBudgetPct" type="number" min="0" max="100" step="1" value="${escapeHtml(draft.segmentSemanticValidationBudgetPct)}" />
              </label>
              <label class="field">
                Semantic validation max segments
                <input data-settings-field="segmentSemanticValidationMaxSegments" type="number" min="0" step="1" value="${escapeHtml(draft.segmentSemanticValidationMaxSegments)}" />
              </label>
              <label class="field">
                Semantic max adjustment (sec)
                <input data-settings-field="segmentSemanticMaxAdjustmentSec" type="number" min="0.25" step="0.25" value="${escapeHtml(draft.segmentSemanticMaxAdjustmentSec)}" />
              </label>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1.5rem;">
              ${renderCheckbox("aiCacheEnabled", draft.aiCacheEnabled, "Enable AI cache")}
              ${renderCheckbox("audioEnabled", draft.audioEnabled, "Enable audio extraction")}
              ${renderCheckbox("deduplicationEnabled", draft.deduplicationEnabled, "Enable deduplication")}
              ${renderCheckbox("clipEnabled", draft.clipEnabled, "Enable CLIP semantic scoring")}
              ${renderCheckbox("segmentBoundaryRefinementEnabled", draft.segmentBoundaryRefinementEnabled, "Enable boundary refinement")}
              ${renderCheckbox("segmentLegacyFallbackEnabled", draft.segmentLegacyFallbackEnabled, "Enable legacy fallback")}
              ${renderCheckbox("segmentSemanticValidationEnabled", draft.segmentSemanticValidationEnabled, "Enable semantic boundary validation")}
            </div>
          </section>
        </div>

        <div class="action-row dialog-actions">
          <button data-action="cancel-settings" class="button secondary" ${appState.settingsBusy ? "disabled" : ""}>Cancel</button>
          <button data-action="save-settings" class="button" ${appState.settingsBusy ? "disabled" : ""}>
            ${appState.settingsBusy ? "Saving..." : "Save settings"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderProviderOption(value: AIProvider, currentValue: AIProvider) {
  const label = value === "lmstudio" ? "LM Studio" : value === "mlx-vlm-local" ? "MLX-VLM Local" : "Deterministic";
  return `<option value="${value}" ${currentValue === value ? "selected" : ""}>${label}</option>`;
}

function renderCheckbox(field: string, checked: boolean, label: string) {
  return `
    <label class="checkbox-field">
      <input data-settings-field="${field}" type="checkbox" ${checked ? "checked" : ""} />
      <span>${label}</span>
    </label>
  `;
}
