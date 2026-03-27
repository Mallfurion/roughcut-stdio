import type { AppSettings, AppState, ProcessState } from "./types.ts";

export const MEDIA_STORAGE_KEY = "roughcut-stdio.desktop.media-dir.v1";

export function createDefaultSettings(): AppSettings {
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
    transcriptProvider: "auto",
    transcriptModelSize: "small",
    audioEnabled: true,
    deduplicationEnabled: true,
    dedupThreshold: "0.85",
    clipEnabled: true,
    clipMinScore: "0.35",
    vlmBudgetPct: "100",
    segmentBoundaryRefinementEnabled: true,
    segmentLegacyFallbackEnabled: true,
    segmentSemanticValidationEnabled: true,
    segmentSemanticAmbiguityThreshold: "0.6",
    segmentSemanticValidationBudgetPct: "100",
    segmentSemanticValidationMaxSegments: "2",
    segmentSemanticMaxAdjustmentSec: "1.5",
  };
}

export function createInitialProcessState(): ProcessState {
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
    error: null,
  };
}

export function createInitialAppState(): AppState {
  return {
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
    reviewBusy: false,
    exportPath: "",
    exportBusy: false,
    exportMessage: "",
    timelinePreviewOpen: false,
  };
}

export function persistMediaDir(mediaDir: string) {
  localStorage.setItem(MEDIA_STORAGE_KEY, mediaDir);
}

export function clearPersistedMediaDir() {
  localStorage.removeItem(MEDIA_STORAGE_KEY);
}

export function hasGeneratedResults(state: Pick<AppState, "project">) {
  return Boolean(state.project && state.project.source === "generated");
}
