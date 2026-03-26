import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { confirm, open, save } from "@tauri-apps/plugin-dialog";
import { buildSegmentReviewModel } from "./review-model.ts";
import "./styles.css";

type Step = "choose" | "process" | "results";
type AIMode = "fast" | "full";
type AIProvider = "deterministic" | "lmstudio" | "mlx-vlm-local";

type ProcessState = {
  running: boolean;
  status: string;
  processed: number;
  total: number;
  current_asset: string;
  elapsed: string;
  eta: string;
  logs: string[];
  output_path?: string | null;
  error?: string | null;
};

type MediaFolderSummary = {
  path: string;
  video_count: number;
};

type QualityMetrics = {
  sharpness: number;
  stability: number;
  visual_novelty: number;
  subject_clarity: number;
  motion_energy: number;
  duration_fit: number;
  speech_presence: number;
  hook_strength: number;
  story_alignment: number;
  audio_energy?: number;
  speech_ratio?: number;
};

type SegmentEvidence = {
  keyframe_paths: string[];
  keyframe_timestamps_sec: number[];
  context_window_start_sec: number;
  context_window_end_sec: number;
};

type SegmentPrefilter = {
  score: number;
  shortlisted: boolean;
  filtered_before_vlm: boolean;
  selection_reason: string;
  deduplicated?: boolean;
  dedup_group_id?: number;
  clip_gated?: boolean;
  vlm_budget_capped?: boolean;
  metrics_snapshot?: Record<string, number>;
};

type SegmentUnderstanding = {
  provider: string;
  keep_label: string;
  confidence: number;
  summary: string;
  rationale: string;
  story_roles: string[];
  shot_type: string;
  camera_motion: string;
  mood: string;
  risk_flags: string[];
};

type SegmentReviewState = {
  shortlisted: boolean;
  filtered_before_vlm: boolean;
  clip_scored: boolean;
  clip_score?: number | null;
  clip_gated?: boolean;
  deduplicated?: boolean;
  dedup_group_id?: number | null;
  vlm_budget_capped?: boolean;
  model_analyzed?: boolean;
  deterministic_fallback?: boolean;
  evidence_keyframe_count?: number;
  analysis_path_summary?: string;
  blocked_reason?: string;
};

type Asset = {
  id: string;
  name: string;
  source_path: string;
  has_proxy?: boolean;
  has_speech: boolean;
  interchange_reel_name: string;
};

type CandidateSegment = {
  id: string;
  asset_id: string;
  start_sec: number;
  end_sec: number;
  analysis_mode: "speech" | "visual";
  description: string;
  transcript_excerpt: string;
  quality_metrics: QualityMetrics;
  evidence_bundle?: SegmentEvidence;
  prefilter?: SegmentPrefilter;
  ai_understanding?: SegmentUnderstanding;
  review_state?: SegmentReviewState;
};

type TakeRecommendation = {
  id: string;
  candidate_segment_id: string;
  title: string;
  is_best_take: boolean;
  selection_reason: string;
  score_technical?: number;
  score_semantic?: number;
  score_story?: number;
  score_total: number;
  outcome?: string;
  within_asset_rank?: number;
  score_gap_to_winner?: number;
  score_driver_labels?: string[];
  limiting_factor_labels?: string[];
};

type TimelineItem = {
  id: string;
  take_recommendation_id: string;
  trim_in_sec: number;
  trim_out_sec: number;
  label: string;
  notes: string;
  source_asset_path: string;
  source_reel: string;
};

type TimelineProject = {
  project: {
    name: string;
    story_prompt: string;
    status: string;
    analysis_summary?: Record<string, number>;
  };
  assets: Asset[];
  candidate_segments: CandidateSegment[];
  take_recommendations: TakeRecommendation[];
  timeline: {
    id: string;
    version: number;
    story_summary: string;
    items: TimelineItem[];
  };
};

type LoadedProject = {
  project: TimelineProject;
  source: "generated" | "sample";
  file_path: string;
};

type AppSettings = {
  aiProvider: AIProvider;
  projectName: string;
  storyPrompt: string;
  aiMode: AIMode;
  aiTimeoutSec: string;
  aiModel: string;
  aiBaseUrl: string;
  aiModelId: string;
  aiDevice: string;
  aiMaxSegmentsPerAsset: string;
  aiMaxKeyframes: string;
  aiKeyframeMaxWidth: string;
  aiConcurrency: string;
  aiCacheEnabled: boolean;
  audioEnabled: boolean;
  deduplicationEnabled: boolean;
  dedupThreshold: string;
  clipEnabled: boolean;
  clipMinScore: string;
  vlmBudgetPct: string;
};

type AppState = {
  currentStep: Step;
  mediaDir: string;
  aiMode: AIMode;
  settings: AppSettings | null;
  settingsDraft: AppSettings | null;
  settingsOpen: boolean;
  settingsBusy: boolean;
  settingsMessage: string;
  mediaSummary: MediaFolderSummary | null;
  mediaSummaryError: string;
  process: ProcessState;
  processLogsExpanded: boolean;
  expandedClipIds: string[];
  allClipsExpanded: boolean;
  project: LoadedProject | null;
  exportPath: string;
  exportBusy: boolean;
  exportMessage: string;
};

const MEDIA_STORAGE_KEY = "roughcut-stdio.desktop.media-dir.v1";

function createDefaultSettings(): AppSettings {
  return {
    aiProvider: "deterministic",
    projectName: "Roughcut Stdio Project",
    storyPrompt: "Build a coherent rough cut from the strongest visual and spoken beats.",
    aiMode: "fast",
    aiTimeoutSec: "45",
    aiModel: "qwen3.5-9b",
    aiBaseUrl: "http://127.0.0.1:1234/v1",
    aiModelId: "mlx-community/Qwen3.5-0.8B-4bit",
    aiDevice: "auto",
    aiMaxSegmentsPerAsset: "1",
    aiMaxKeyframes: "1",
    aiKeyframeMaxWidth: "448",
    aiConcurrency: "2",
    aiCacheEnabled: true,
    audioEnabled: true,
    deduplicationEnabled: true,
    dedupThreshold: "0.85",
    clipEnabled: true,
    clipMinScore: "0.35",
    vlmBudgetPct: "100"
  };
}

function createInitialProcessState(): ProcessState {
  return {
    running: false,
    status: "idle",
    processed: 0,
    total: 0,
    current_asset: "",
    elapsed: "00:00",
    eta: "00:00",
    logs: [],
    output_path: null,
    error: null
  };
}

const appState: AppState = {
  currentStep: "choose",
  mediaDir: localStorage.getItem(MEDIA_STORAGE_KEY) ?? "",
  aiMode: "fast",
  settings: null,
  settingsDraft: null,
  settingsOpen: false,
  settingsBusy: false,
  settingsMessage: "",
  mediaSummary: null,
  mediaSummaryError: "",
  process: createInitialProcessState(),
  processLogsExpanded: false,
  expandedClipIds: [],
  allClipsExpanded: false,
  project: null,
  exportPath: "",
  exportBusy: false,
  exportMessage: ""
};

let processPollTimer: number | null = null;

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing app root");
}

render();
void bootstrap();

async function bootstrap() {
  try {
    await listen<ProcessState>("process-update", (event) => {
      appState.process = event.payload;
      if (appState.process.running) {
        appState.currentStep = "process";
        ensureProcessPolling();
      } else {
        stopProcessPolling();
      }
      if (appState.process.status === "completed") {
        void handleProcessCompleted();
      } else {
        render();
      }
    });
  } catch (error) {
    pushProcessLog(`Process event listener unavailable: ${stringifyError(error)}`);
  }

  try {
    await refreshSettings();
  } catch (error) {
    pushProcessLog(`Settings load failed: ${stringifyError(error)}`);
  }

  try {
    appState.process = await invoke<ProcessState>("get_process_state");
  } catch (error) {
    pushProcessLog(`Initial process state unavailable: ${stringifyError(error)}`);
  }

  try {
    await refreshProject();
  } catch (error) {
    pushProcessLog(`Project load failed: ${stringifyError(error)}`);
  }

  try {
    await refreshMediaSummary();
  } catch (error) {
    pushProcessLog(`Media folder inspection failed: ${stringifyError(error)}`);
  }

  if (appState.process.running) {
    appState.currentStep = "process";
    ensureProcessPolling();
  } else if (hasGeneratedResults()) {
    appState.currentStep = "results";
  }

  render();
}

function persistMediaDir() {
  localStorage.setItem(MEDIA_STORAGE_KEY, appState.mediaDir);
}

function hasGeneratedResults() {
  return Boolean(appState.project && appState.project.source === "generated");
}

function pushProcessLog(message: string) {
  appState.process.logs.push(message);
  if (appState.process.logs.length > 200) {
    appState.process.logs.splice(0, appState.process.logs.length - 200);
  }
}

async function refreshProject() {
  try {
    appState.project = await invoke<LoadedProject>("load_active_project");
  } catch {
    appState.project = null;
  }
}

async function refreshSettings() {
  const settings = await invoke<AppSettings>("load_app_settings");
  appState.settings = settings;
  appState.aiMode = settings.aiMode;
}

function openSettingsDialog() {
  appState.settingsDraft = { ...(appState.settings ?? createDefaultSettings()) };
  appState.settingsOpen = true;
  appState.settingsMessage = "";
  render();
}

function closeSettingsDialog() {
  appState.settingsOpen = false;
  appState.settingsDraft = null;
  appState.settingsBusy = false;
  appState.settingsMessage = "";
  render();
}

async function refreshMediaSummary() {
  if (!appState.mediaDir.trim()) {
    appState.mediaSummary = null;
    appState.mediaSummaryError = "";
    return;
  }

  appState.mediaSummaryError = "Loading video count...";
  render();

  try {
    appState.mediaSummary = await invoke<MediaFolderSummary>("inspect_media_folder", {
      path: appState.mediaDir
    });
    appState.mediaSummaryError = "";
  } catch (error) {
    appState.mediaSummary = null;
    appState.mediaSummaryError = stringifyError(error);
    pushProcessLog(`Media folder inspection failed: ${appState.mediaSummaryError}`);
  }
}

async function syncProcessState() {
  try {
    appState.process = await invoke<ProcessState>("get_process_state");
    if (!appState.process.running) {
      stopProcessPolling();
    }
    if (appState.process.status === "completed") {
      await handleProcessCompleted();
      return;
    }
  } catch (error) {
    pushProcessLog(`Process state refresh failed: ${stringifyError(error)}`);
    stopProcessPolling();
  }

  render();
}

async function handleProcessCompleted() {
  await refreshProject();
  appState.currentStep = hasGeneratedResults() ? "results" : "process";
  if (hasGeneratedResults() && appState.expandedClipIds.length === 0) {
    const firstAssetId = appState.project?.project.assets?.[0]?.id;
    appState.expandedClipIds = firstAssetId ? [firstAssetId] : [];
  }
  render();
}

function ensureProcessPolling() {
  if (processPollTimer !== null) {
    return;
  }
  processPollTimer = window.setInterval(() => {
    void syncProcessState();
  }, 1000);
}

function stopProcessPolling() {
  if (processPollTimer === null) {
    return;
  }
  window.clearInterval(processPollTimer);
  processPollTimer = null;
}

async function resetWorkflow() {
  const confirmed = await confirm("Go back to step 1 and reset the current desktop workflow state? This clears the selected folder and in-app results view, and deletes the generated folder.", {
    title: "Reset workflow",
    kind: "warning"
  });
  if (!confirmed) {
    return;
  }

  try {
    await invoke("clean_generated");
  } catch (error) {
    pushProcessLog(`Failed to clean generated folder: ${stringifyError(error)}`);
  }

  stopProcessPolling();
  appState.currentStep = "choose";
  appState.mediaDir = "";
  appState.aiMode = appState.settings?.aiMode ?? "fast";
  appState.mediaSummary = null;
  appState.mediaSummaryError = "";
  appState.process = createInitialProcessState();
  appState.expandedClipIds = [];
  appState.project = null;
  appState.exportPath = "";
  appState.exportBusy = false;
  appState.exportMessage = "";
  appState.processLogsExpanded = false;
  localStorage.removeItem(MEDIA_STORAGE_KEY);
  render();
}

function goToProcessStep() {
  if (!appState.mediaDir.trim()) {
    return;
  }
  appState.currentStep = "process";
  render();
}

function goToResultsStep() {
  if (!hasGeneratedResults()) {
    return;
  }
  appState.currentStep = "results";
  if (appState.expandedClipIds.length === 0) {
    const firstAssetId = appState.project?.project.assets?.[0]?.id;
    appState.expandedClipIds = firstAssetId ? [firstAssetId] : [];
  }
  render();
}

function render() {
  app.innerHTML = `
    <main class="shell">
      <section class="stepper card">
        <div class="stepper-layout">
          <button
            id="reset-workflow"
            class="icon-button"
            title="Back to step 1"
            aria-label="Back to step 1"
            ${appState.currentStep === "choose" ? "disabled" : ""}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 7H4v4" />
              <path d="M4 11a8 8 0 1 0 2.3-5.6L4 7" />
            </svg>
          </button>
          <div class="stepper-track">
            ${renderStepChip("choose", "1", "Choose folder")}
            ${renderStepChip("process", "2", "Process videos")}
            ${renderStepChip("results", "3", "View results")}
          </div>
          <button
            id="open-settings"
            class="icon-button"
            title="Settings"
            aria-label="Settings"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3.75 13.5 6l2.62.58-.75 2.57 1.8 1.95-1.8 1.95.75 2.57L13.5 18 12 20.25 10.5 18l-2.62-.58.75-2.57-1.8-1.95 1.8-1.95-.75-2.57L10.5 6 12 3.75Z" />
              <circle cx="12" cy="12" r="2.75" />
            </svg>
          </button>
        </div>
      </section>

      ${renderCurrentStep()}
      ${renderSettingsDialog()}
    </main>
  `;

  bindActions();
}

function renderCurrentStep() {
  switch (appState.currentStep) {
    case "process":
      return renderProcessStep();
    case "results":
      return renderResultsStep();
    default:
      return renderChooseStep();
  }
}

function renderChooseStep() {
  const canContinue = Boolean(appState.mediaDir.trim());
  const videoCountPill = canContinue ? `<span class="pill header-pill">videos: ${escapeHtml(appState.mediaSummary ? String(appState.mediaSummary.video_count) : "unknown")}</span>` : "";
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
        <button id="pick-media" class="button secondary">Choose media folder</button>
        <button id="continue-process" class="button" ${!canContinue ? "disabled" : ""}>Continue to processing</button>
      </div>
    </section>
  `;
}

function renderSettingsDialog() {
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
          <button id="close-settings" class="icon-button" title="Close settings" aria-label="Close settings">
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
                <select id="settings-ai-provider">
                  <option value="deterministic" ${provider === "deterministic" ? "selected" : ""}>Deterministic</option>
                  <option value="lmstudio" ${provider === "lmstudio" ? "selected" : ""}>LM Studio</option>
                  <option value="mlx-vlm-local" ${provider === "mlx-vlm-local" ? "selected" : ""}>MLX-VLM Local</option>
                </select>
              </label>
              <label class="field">
                AI mode
                <select id="settings-ai-mode">
                  <option value="fast" ${draft.aiMode === "fast" ? "selected" : ""}>Fast</option>
                  <option value="full" ${draft.aiMode === "full" ? "selected" : ""}>Full</option>
                </select>
              </label>
              <label class="field">
                Project name
                <input id="settings-project-name" type="text" value="${escapeHtml(draft.projectName)}" />
              </label>
              <label class="field">
                Story prompt
                <textarea id="settings-story-prompt" rows="4">${escapeHtml(draft.storyPrompt)}</textarea>
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
                  <input id="settings-ai-model" type="text" value="${escapeHtml(draft.aiModel)}" />
                </label>
                <label class="field">
                  LM Studio base URL
                  <input id="settings-ai-base-url" type="text" value="${escapeHtml(draft.aiBaseUrl)}" />
                </label>`
                  : ""
              }
              ${
                provider === "mlx-vlm-local"
                  ? `
                <label class="field">
                  MLX-VLM model ID
                  <input id="settings-ai-model-id" type="text" value="${escapeHtml(draft.aiModelId)}" />
                </label>
                <label class="field">
                  MLX-VLM device
                  <select id="settings-ai-device">
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
                <input id="settings-ai-timeout-sec" type="number" min="1" value="${escapeHtml(draft.aiTimeoutSec)}" />
              </label>
              <label class="field">
                Max segments per asset
                <input id="settings-ai-max-segments" type="number" min="1" value="${escapeHtml(draft.aiMaxSegmentsPerAsset)}" />
              </label>
              <label class="field">
                Max keyframes per segment
                <input id="settings-ai-max-keyframes" type="number" min="1" value="${escapeHtml(draft.aiMaxKeyframes)}" />
              </label>
              <label class="field">
                Keyframe max width
                <input id="settings-ai-keyframe-width" type="number" min="160" value="${escapeHtml(draft.aiKeyframeMaxWidth)}" />
              </label>
              <label class="field">
                AI concurrency
                <input id="settings-ai-concurrency" type="number" min="1" value="${escapeHtml(draft.aiConcurrency)}" />
              </label>
              <label class="field">
                Dedup threshold
                <input id="settings-dedup-threshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(draft.dedupThreshold)}" />
              </label>
              <label class="field">
                CLIP min score
                <input id="settings-clip-min-score" type="number" min="0" max="1" step="0.01" value="${escapeHtml(draft.clipMinScore)}" />
              </label>
              <label class="field">
                VLM budget %
                <input id="settings-vlm-budget-pct" type="number" min="0" max="100" step="1" value="${escapeHtml(draft.vlmBudgetPct)}" />
              </label>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1.5rem;">
              <label class="checkbox-field">
                <input id="settings-ai-cache" type="checkbox" ${draft.aiCacheEnabled ? "checked" : ""} />
                <span>Enable AI cache</span>
              </label>
              <label class="checkbox-field">
                <input id="settings-audio-enabled" type="checkbox" ${draft.audioEnabled ? "checked" : ""} />
                <span>Enable audio extraction</span>
              </label>
              <label class="checkbox-field">
                <input id="settings-deduplication-enabled" type="checkbox" ${draft.deduplicationEnabled ? "checked" : ""} />
                <span>Enable deduplication</span>
              </label>
              <label class="checkbox-field">
                <input id="settings-clip-enabled" type="checkbox" ${draft.clipEnabled ? "checked" : ""} />
                <span>Enable CLIP semantic scoring</span>
              </label>
            </div>
          </section>
        </div>

        <div class="action-row dialog-actions">
          <button id="cancel-settings" class="button secondary" ${appState.settingsBusy ? "disabled" : ""}>Cancel</button>
          <button id="save-settings" class="button" ${appState.settingsBusy ? "disabled" : ""}>
            ${appState.settingsBusy ? "Saving..." : "Save settings"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderProcessStep() {
  const processPercent = appState.process.total ? Math.max(0, Math.min(100, Math.round((appState.process.processed / appState.process.total) * 100))) : 0;
  const canViewResults = hasGeneratedResults() && !appState.process.running;

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
          <select id="ai-mode-select">
            <option value="fast" ${appState.aiMode === "fast" ? "selected" : ""}>Fast</option>
            <option value="full" ${appState.aiMode === "full" ? "selected" : ""}>Full</option>
          </select>
        </label>
      </div>

      <div class="summary-grid">
        ${metric("Folder", appState.mediaDir || "Missing")}
        ${metric("Videos", appState.mediaSummary ? String(appState.mediaSummary.video_count) : "Unknown")}
        ${metric("AI mode", appState.aiMode)}
      </div>

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
        <button id="start-process" class="button" ${!appState.mediaDir || appState.process.running ? "disabled" : ""}>
          ${appState.process.running ? "Processing..." : "Start process"}
        </button>
        <button id="view-results" class="button secondary" ${!canViewResults ? "disabled" : ""}>View results</button>
        <button id="toggle-logs" class="button secondary">
          ${appState.processLogsExpanded ? "Hide Logs" : "Show Logs"}
        </button>
      </div>

      ${appState.processLogsExpanded ? `<pre id="process-log" class="log-box log-box-large">${escapeHtml(appState.process.logs.join("\n"))}</pre>` : ""}
    </section>
  `;
}

function renderResultsStep() {
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
  const vlmAnalyzedCount = (analysisSummary.ai_live_segment_count ?? 0) + (analysisSummary.ai_cached_segment_count ?? 0);

  return `
    <section class="card view-card">
      <div class="view-head">
        <div>
          <p class="eyebrow">Step 3</p>
          <h2>View results</h2>
          <p class="muted">Review the selected shots and export the generated timeline.</p>
        </div>
        <div class="action-row">
          <button id="export-timeline" class="button" ${appState.exportBusy ? "disabled" : ""}>
            ${appState.exportBusy ? "Exporting..." : "Export to Davinci Resolve Timeline"}
          </button>
        </div>
      </div>

      <p class="status ${appState.exportMessage ? "ok" : ""}">
        ${escapeHtml(appState.exportMessage || "Export the current generated timeline to an FCPXML file for DaVinci Resolve.")}
      </p>

      <div class="review-summary">
        <div class="review-summary-metrics">
          ${metric("Project", project.project.name)}
          ${metric("Clips", String(clipViews.length))}
          ${metric("Sections", String(project.candidate_segments.length))}
          ${metric("VLM analyzed", String(vlmAnalyzedCount))}
        </div>
        <button id="toggle-all-clips" class="icon-button" title="${appState.allClipsExpanded ? "Collapse all" : "Expand all"}" aria-label="${appState.allClipsExpanded ? "Collapse all clips" : "Expand all clips"}">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            ${appState.allClipsExpanded ? '<path d="M19 13H5v-2h14v2Z" />' : '<path d="M4 14h6v6h2v-6h6v-2h-6V6h-2v6H4v2Z" />'}
          </svg>
        </button>
      </div>

      <div class="clip-grid">
        ${clipViews.map(renderClipCard).join("")}
      </div>
    </section>
  `;
}

function renderStepChip(step: Step, number: string, label: string) {
  const status = step === appState.currentStep ? "current" : stepCompleted(step) ? "done" : "";
  return `
    <article class="step-chip ${status}">
      <span class="step-index">${number}</span>
      <div>
        <strong>${label}</strong>
      </div>
    </article>
  `;
}

function stepCompleted(step: Step) {
  if (step === "choose") {
    return Boolean(appState.mediaDir.trim());
  }
  if (step === "process") {
    return hasGeneratedResults();
  }
  return false;
}

function metric(label: string, value: string) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function updateSettingsDraft(patch: Partial<AppSettings>) {
  if (!appState.settingsDraft) {
    return;
  }
  appState.settingsDraft = {
    ...appState.settingsDraft,
    ...patch
  };
}

function bindActions() {
  const openSettings = document.getElementById("open-settings");
  if (openSettings) {
    openSettings.onclick = () => {
      openSettingsDialog();
    };
  }

  const pickMedia = document.getElementById("pick-media");
  if (pickMedia) {
    pickMedia.onclick = async () => {
      try {
        const selected = await open({
          directory: true,
          multiple: false,
          title: "Choose the media folder for Roughcut Stdio"
        });
        console.log("[roughcut-stdio] media folder picker result:", selected);
        if (typeof selected === "string" && selected.trim()) {
          appState.mediaDir = selected;
          persistMediaDir();
          appState.exportMessage = "";
          pushProcessLog(`Selected media folder: ${selected}`);
          await refreshMediaSummary();
          render();
        }
      } catch (error) {
        pushProcessLog(`Media folder selection failed: ${stringifyError(error)}`);
        render();
      }
    };
  }

  const continueProcess = document.getElementById("continue-process");
  if (continueProcess) {
    continueProcess.onclick = () => {
      goToProcessStep();
    };
  }

  const startProcess = document.getElementById("start-process");
  if (startProcess) {
    startProcess.onclick = async () => {
      appState.currentStep = "process";
      appState.process = {
        ...createInitialProcessState(),
        running: true,
        status: "starting",
        logs: ["Starting process run..."]
      };
      render();

      try {
        await invoke("start_process", {
          request: {
            mediaDir: appState.mediaDir,
            aiMode: appState.aiMode
          }
        });
        ensureProcessPolling();
      } catch (error) {
        appState.process.error = stringifyError(error);
        appState.process.running = false;
        appState.process.status = "failed";
        pushProcessLog(`Process failed to start: ${appState.process.error}`);
        render();
      }
    };
  }

  const aiModeSelect = document.getElementById("ai-mode-select") as HTMLSelectElement | null;
  if (aiModeSelect) {
    aiModeSelect.onchange = () => {
      appState.aiMode = aiModeSelect.value === "full" ? "full" : "fast";
      if (appState.settings) {
        appState.settings = {
          ...appState.settings,
          aiMode: appState.aiMode
        };
      }
      render();
    };
  }

  const viewResults = document.getElementById("view-results");
  if (viewResults) {
    viewResults.onclick = () => {
      goToResultsStep();
    };
  }

  const toggleLogs = document.getElementById("toggle-logs");
  if (toggleLogs) {
    toggleLogs.onclick = () => {
      appState.processLogsExpanded = !appState.processLogsExpanded;
      render();
    };
  }

  const exportButton = document.getElementById("export-timeline");
  if (exportButton) {
    exportButton.onclick = async () => {
      appState.exportBusy = true;
      appState.exportMessage = "";
      render();
      try {
        const targetPath = await save({
          title: "Export DaVinci Resolve Timeline",
          defaultPath: "roughcut-stdio.fcpxml"
        });
        if (!targetPath) {
          appState.exportBusy = false;
          render();
          return;
        }
        const exported = await invoke<string>("export_timeline", {
          targetPath
        });
        appState.exportPath = exported;
        appState.exportMessage = `Exported Resolve timeline to ${exported}`;
      } catch (error) {
        appState.exportMessage = `Export failed: ${stringifyError(error)}`;
      } finally {
        appState.exportBusy = false;
        render();
      }
    };
  }

  const toggleAllClipsButton = document.getElementById("toggle-all-clips");
  if (toggleAllClipsButton) {
    toggleAllClipsButton.onclick = () => {
      toggleAllClips();
    };
  }

  document.querySelectorAll<HTMLElement>("#reset-workflow").forEach((element) => {
    element.onclick = async () => {
      await resetWorkflow();
    };
  });

  document.querySelectorAll<HTMLElement>(".clip-toggle").forEach((element) => {
    element.onclick = () => {
      const clipId = element.dataset.clipId;
      if (!clipId) {
        return;
      }
      if (appState.expandedClipIds.includes(clipId)) {
        appState.expandedClipIds = appState.expandedClipIds.filter((value) => value !== clipId);
      } else {
        appState.expandedClipIds = [...appState.expandedClipIds, clipId];
      }
      render();
    };
  });

  const closeSettings = document.getElementById("close-settings");
  if (closeSettings) {
    closeSettings.onclick = () => {
      closeSettingsDialog();
    };
  }

  const cancelSettings = document.getElementById("cancel-settings");
  if (cancelSettings) {
    cancelSettings.onclick = () => {
      closeSettingsDialog();
    };
  }

  const settingsProvider = document.getElementById("settings-ai-provider") as HTMLSelectElement | null;
  if (settingsProvider) {
    settingsProvider.onchange = () => {
      updateSettingsDraft({
        aiProvider: settingsProvider.value as AIProvider
      });
      render();
    };
  }

  const settingsAIMode = document.getElementById("settings-ai-mode") as HTMLSelectElement | null;
  if (settingsAIMode) {
    settingsAIMode.onchange = () => {
      updateSettingsDraft({
        aiMode: settingsAIMode.value === "full" ? "full" : "fast"
      });
    };
  }

  bindTextSetting("settings-project-name", (value) => updateSettingsDraft({ projectName: value }));
  bindTextSetting("settings-story-prompt", (value) => updateSettingsDraft({ storyPrompt: value }));
  bindTextSetting("settings-ai-model", (value) => updateSettingsDraft({ aiModel: value }));
  bindTextSetting("settings-ai-base-url", (value) => updateSettingsDraft({ aiBaseUrl: value }));
  bindTextSetting("settings-ai-model-id", (value) => updateSettingsDraft({ aiModelId: value }));
  bindTextSetting("settings-ai-timeout-sec", (value) => updateSettingsDraft({ aiTimeoutSec: value }));
  bindTextSetting("settings-ai-max-segments", (value) => updateSettingsDraft({ aiMaxSegmentsPerAsset: value }));
  bindTextSetting("settings-ai-max-keyframes", (value) => updateSettingsDraft({ aiMaxKeyframes: value }));
  bindTextSetting("settings-ai-keyframe-width", (value) => updateSettingsDraft({ aiKeyframeMaxWidth: value }));
  bindTextSetting("settings-ai-concurrency", (value) => updateSettingsDraft({ aiConcurrency: value }));

  const settingsAIDevice = document.getElementById("settings-ai-device") as HTMLSelectElement | null;
  if (settingsAIDevice) {
    settingsAIDevice.onchange = () => {
      updateSettingsDraft({ aiDevice: settingsAIDevice.value });
    };
  }

  const settingsAICache = document.getElementById("settings-ai-cache") as HTMLInputElement | null;
  if (settingsAICache) {
    settingsAICache.onchange = () => {
      updateSettingsDraft({ aiCacheEnabled: settingsAICache.checked });
    };
  }

  const settingsAudioEnabled = document.getElementById("settings-audio-enabled") as HTMLInputElement | null;
  if (settingsAudioEnabled) {
    settingsAudioEnabled.onchange = () => {
      updateSettingsDraft({ audioEnabled: settingsAudioEnabled.checked });
    };
  }

  const settingsDeduplicationEnabled = document.getElementById("settings-deduplication-enabled") as HTMLInputElement | null;
  if (settingsDeduplicationEnabled) {
    settingsDeduplicationEnabled.onchange = () => {
      updateSettingsDraft({ deduplicationEnabled: settingsDeduplicationEnabled.checked });
    };
  }

  bindTextSetting("settings-dedup-threshold", (value) => updateSettingsDraft({ dedupThreshold: value }));

  const settingsClipEnabled = document.getElementById("settings-clip-enabled") as HTMLInputElement | null;
  if (settingsClipEnabled) {
    settingsClipEnabled.onchange = () => {
      updateSettingsDraft({ clipEnabled: settingsClipEnabled.checked });
    };
  }

  bindTextSetting("settings-clip-min-score", (value) => updateSettingsDraft({ clipMinScore: value }));
  bindTextSetting("settings-vlm-budget-pct", (value) => updateSettingsDraft({ vlmBudgetPct: value }));

  const saveSettings = document.getElementById("save-settings");
  if (saveSettings) {
    saveSettings.onclick = async () => {
      if (!appState.settingsDraft) {
        return;
      }
      appState.settingsBusy = true;
      appState.settingsMessage = "";
      render();
      try {
        const saved = await invoke<AppSettings>("save_app_settings", {
          settings: appState.settingsDraft
        });
        appState.settings = saved;
        appState.aiMode = saved.aiMode;
        appState.settingsDraft = { ...saved };
        appState.settingsBusy = false;
        appState.settingsMessage = "Saved settings to .env";
        render();
      } catch (error) {
        appState.settingsBusy = false;
        appState.settingsMessage = `Save failed: ${stringifyError(error)}`;
        render();
      }
    };
  }

  syncProcessLogScroll();
}

function bindTextSetting(id: string, apply: (value: string) => void) {
  const element = document.getElementById(id) as HTMLInputElement | HTMLTextAreaElement | null;
  if (!element) {
    return;
  }
  element.oninput = () => {
    apply(element.value);
  };
}

function resolveClipViews(project: TimelineProject) {
  const takeBySegmentId = new Map(
    project.take_recommendations.map((take) => [take.candidate_segment_id, take]),
  );
  return project.assets
    .map((asset) => ({
      asset,
      segments: project.candidate_segments
        .filter((segment) => segment.asset_id === asset.id)
        .sort((left, right) => left.start_sec - right.start_sec)
        .map((segment) => ({
          segment,
          recommendation: takeBySegmentId.get(segment.id),
        })),
    }))
    .filter((view) => view.segments.length > 0);
}

function renderClipCard(view: { asset: Asset; segments: { segment: CandidateSegment; recommendation?: TakeRecommendation }[] }) {
  const expanded = appState.expandedClipIds.includes(view.asset.id);
  const dedupCount = view.segments.filter(({ segment }) => segment.prefilter?.deduplicated).length;
  const activCount = view.segments.length - dedupCount;

  return `
    <article class="clip-card">
      <button class="clip-toggle" data-clip-id="${escapeHtml(view.asset.id)}" aria-expanded="${expanded ? "true" : "false"}">
        <div class="clip-head">
          <div>
            <h3>${escapeHtml(view.asset.name)}</h3>
            <p class="muted">${escapeHtml(view.asset.interchange_reel_name)}</p>
          </div>
          <div class="clip-toggle-meta">
            <span class="pill">${view.segments.length} sections</span>
            ${dedupCount > 0 ? `<span class="pill pill-dedup-info">${activCount} active, ${dedupCount} dup</span>` : ""}
            <span class="clip-chevron">${expanded ? "−" : "+"}</span>
          </div>
        </div>
      </button>
      ${
        expanded
          ? `
      <div class="section-list">
        ${view.segments.map(renderSegmentCard).join("")}
      </div>`
          : ""
      }
    </article>
  `;
}

function renderSegmentCard(view: { segment: CandidateSegment; recommendation?: TakeRecommendation }) {
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
  const quietFacts = [
    score > 0 ? `Prefilter ${formatScore(score)}` : "",
    clipScore !== undefined ? `CLIP ${formatScore(clipScore)}` : "",
    evidence ? `${evidence.keyframe_timestamps_sec.length} keyframe${evidence.keyframe_timestamps_sec.length === 1 ? "" : "s"}` : "",
    evidence ? `Context ${formatSegmentRange(evidence.context_window_start_sec, evidence.context_window_end_sec)}` : "",
    typeof ai?.confidence === "number" ? `Confidence ${Math.round(ai.confidence * 100)}%` : "",
    ai?.keep_label && ai.keep_label !== "n/a" ? `VLM ${ai.keep_label}` : "",
    !isDeduplicated && dedupGroupId !== undefined ? `Dedup keeper G${dedupGroupId}` : "",
  ].filter(Boolean);
  const secondaryRationale = ai?.rationale && ai.rationale !== review.decisionSummary ? ai.rationale : "";
  const tonalMeta = [ai?.shot_type, ai?.camera_motion, ai?.mood].filter(Boolean);

  return `
    <article class="section-card ${review.outcomeClassName}${isDeduplicated ? " section-card--deduplicated" : ""}">
      <div class="section-head section-head--compact">
        <div class="pill-row pill-row--primary">
          <span class="pill section-pill">${escapeHtml(formatSegmentRange(segment.start_sec, segment.end_sec))}</span>
          <span class="pill section-pill section-outcome-pill section-outcome-pill--${escapeHtml(review.outcome)}">${escapeHtml(review.outcomeLabel)}</span>
          ${providerLabel ? `<span class="pill section-pill">${escapeHtml(providerLabel)}</span>` : ""}
          ${blockedBadge ? `<span class="pill section-pill ${blockedBadge.className}">${escapeHtml(blockedBadge.label)}</span>` : ""}
        </div>
      </div>
      <p class="section-summary section-summary--hero">${escapeHtml(vlmText)}</p>
      ${review.decisionSummary ? `<p class="section-recommendation">${escapeHtml(review.decisionSummary)}</p>` : ""}
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
      ${review.analysisPathSummary ? `<p class="muted section-analysis-path">${escapeHtml(review.analysisPathSummary)}</p>` : ""}
      ${secondaryRationale ? `<p class="muted section-rationale">${escapeHtml(secondaryRationale)}</p>` : ""}
      <div class="meta-list section-meta">
        ${tonalMeta.map(renderOptionalMeta).join("")}
        ${renderAudioMetrics(segment.prefilter?.metrics_snapshot ?? {})}
      </div>
    </article>
  `;
}

function renderScoreBar(label: string, value: string) {
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

function formatSegmentRange(start: number, end: number) {
  return `${start.toFixed(2)}s - ${end.toFixed(2)}s`;
}

function formatScore(value: number) {
  return `${Math.round(value * 100)}`;
}

function toggleAllClips() {
  appState.allClipsExpanded = !appState.allClipsExpanded;
  if (appState.allClipsExpanded) {
    const project = appState.project?.project;
    if (project) {
      appState.expandedClipIds = project.assets.map((asset) => asset.id);
    }
  } else {
    appState.expandedClipIds = [];
  }
  render();
}

function renderOptionalMeta(value?: string) {
  if (!value) {
    return "";
  }
  return `<span>${escapeHtml(value)}</span>`;
}

function renderAudioMetrics(metrics: Record<string, number> | undefined) {
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

function resolveBlockedBadge(segment: CandidateSegment) {
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

function formatProviderLabel(provider?: string) {
  if (!provider) {
    return "";
  }
  if (provider === "deterministic") {
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

function escapeHtml(value: string | undefined | null) {
  if (!value) return "";
  const str = String(value);
  return str.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function stringifyError(error: unknown) {
  if (typeof error === "string") {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function syncProcessLogScroll() {
  if (!appState.processLogsExpanded) {
    return;
  }
  const logElement = document.getElementById("process-log");
  if (!logElement) {
    return;
  }
  logElement.scrollTop = logElement.scrollHeight;
}
