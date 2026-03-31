import {
  clearPersistedMediaDir,
  createDefaultSettings,
  createInitialAppState,
  createInitialProcessState,
  hasGeneratedResults,
  persistMediaDir,
} from "./state.ts";
import type { AppSettings, ResultsOrdering, TranscriptProvider } from "./types.ts";
import { stringifyError } from "../lib/format.ts";
import { renderAppShell } from "../render/app-shell.ts";
import { resolveClipViews } from "../render/view-models.ts";
import {
  checkRuntimeReady,
  clearBestTake,
  chooseTimelineExportPath,
  cleanGenerated,
  confirmWorkflowReset,
  exportTimeline,
  getProcessState,
  inspectMediaFolder,
  listenProcessUpdate,
  clearBestTakeOverride,
  loadActiveProject,
  loadAppSettings,
  pickMediaDirectory,
  runSetup,
  saveAppSettings,
  selectBestTake,
  startProcess,
} from "../platform/desktop-api.ts";

export function startDesktopApp(appRoot: HTMLDivElement) {
  const appState = createInitialAppState();
  let processPollTimer: number | null = null;
  let renderScheduled = false;

  appRoot.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const actionElement = target.closest<HTMLElement>("[data-action]");
    if (!actionElement) {
      return;
    }
    void handleActionClick(actionElement);
  });

  appRoot.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target instanceof HTMLSelectElement && target.dataset.action === "set-ai-mode") {
      setAIMode(target.value);
      scheduleRender();
      return;
    }

    if (target instanceof HTMLSelectElement && target.dataset.action === "set-results-order") {
      setResultsOrdering(target.value);
      scheduleRender();
      return;
    }

    if (isSettingsField(target)) {
      applySettingsField(target);
      render();
    }
  });

  appRoot.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !isSettingsField(target)) {
      return;
    }
    applySettingsField(target);
  });

  render();
  void bootstrap();

  async function bootstrap() {
    try {
      await listenProcessUpdate((processState) => {
        appState.process = processState;
        if (appState.process.running) {
          appState.currentStep = "process";
          ensureProcessPolling();
        } else {
          stopProcessPolling();
        }

        if (appState.process.status === "completed") {
          void handleProcessCompleted();
          return;
        }

        render();
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
      await refreshRuntimeCheck();
    } catch (error) {
      pushProcessLog(`Runtime check failed: ${stringifyError(error)}`);
    }

    try {
      appState.process = await getProcessState();
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
    } else if (hasGeneratedResults(appState)) {
      appState.currentStep = "results";
    }

    render();
  }

  async function handleActionClick(element: HTMLElement) {
    switch (element.dataset.action) {
      case "open-settings":
        openSettingsDialog();
        return;
      case "close-settings":
      case "cancel-settings":
        closeSettingsDialog();
        return;
      case "pick-media":
        await handlePickMedia();
        return;
      case "prepare-runtime":
        await handlePrepareRuntime();
        return;
      case "apply-runtime-fallback":
        await handleApplyRuntimeFallback();
        return;
      case "refresh-runtime":
        await refreshRuntimeCheck();
        return;
      case "go-process":
        goToProcessStep();
        return;
      case "start-process":
        await handleStartProcess();
        return;
      case "view-results":
        goToResultsStep();
        return;
      case "toggle-logs":
        appState.processLogsExpanded = !appState.processLogsExpanded;
        render();
        return;
      case "export-timeline":
        await handleExportTimeline();
        return;
      case "toggle-all-clips":
        toggleAllClips();
        return;
      case "toggle-timeline-preview":
        appState.timelinePreviewOpen = !appState.timelinePreviewOpen;
        render();
        return;
      case "reset-workflow":
        await resetWorkflow();
        return;
      case "toggle-clip":
        if (element.dataset.clipId) {
          toggleClip(element.dataset.clipId);
        }
        return;
      case "toggle-detail-panel":
        if (element.dataset.panelId) {
          toggleDetailPanel(element.dataset.panelId);
        }
        return;
      case "set-best-take":
        if (element.dataset.assetId && element.dataset.segmentId) {
          await handleSetBestTake(element.dataset.assetId, element.dataset.segmentId);
        }
        return;
      case "clear-best-take":
        if (element.dataset.assetId) {
          await handleClearBestTake(element.dataset.assetId);
        }
        return;
      case "clear-best-take-override":
        if (element.dataset.assetId) {
          await handleClearBestTakeOverride(element.dataset.assetId);
        }
        return;
      case "save-settings":
        await handleSaveSettings();
        return;
      default:
        return;
    }
  }

  function render() {
    try {
      appRoot.innerHTML = renderAppShell(appState);
      syncProcessLogScroll();
    } catch (error) {
      const message = stringifyError(error);
      console.error("[roughcut-stdio] render failed", error);
      appRoot.innerHTML = `
        <main class="shell">
          <section class="card view-card">
            <div class="view-head">
              <div>
                <p class="eyebrow">Desktop error</p>
                <h2>Render failed</h2>
                <p class="muted">The app hit a frontend render error.</p>
              </div>
            </div>
            <pre class="empty-state">${message}</pre>
          </section>
        </main>
      `;
    }
  }

  function scheduleRender() {
    if (renderScheduled) {
      return;
    }
    renderScheduled = true;
    window.requestAnimationFrame(() => {
      renderScheduled = false;
      render();
    });
  }

  function pushProcessLog(message: string) {
    appState.process.logs.push(message);
    if (appState.process.logs.length > 200) {
      appState.process.logs.splice(0, appState.process.logs.length - 200);
    }
  }

  async function refreshProject() {
    try {
      appState.project = await loadActiveProject();
    } catch {
      appState.project = null;
    }
  }

  async function refreshSettings() {
    const settings = await loadAppSettings();
    appState.settings = settings;
    appState.aiMode = settings.aiMode;
  }

  async function refreshRuntimeCheck() {
    if (!appState.settings) {
      return;
    }

    appState.runtimeBusy = true;
    render();

    try {
      appState.runtimeCheck = await checkRuntimeReady(buildRuntimeConfig(appState.settings));
      if (appState.runtimeCheck.runtime_ready && !appState.runtimeCheck.bootstrap_required) {
        appState.runtimeMessage = "";
      }
    } finally {
      appState.runtimeBusy = false;
      render();
    }
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
      appState.mediaSummary = await inspectMediaFolder(appState.mediaDir);
      appState.mediaSummaryError = "";
    } catch (error) {
      appState.mediaSummary = null;
      appState.mediaSummaryError = stringifyError(error);
      pushProcessLog(`Media folder inspection failed: ${appState.mediaSummaryError}`);
    }
  }

  async function syncProcessState() {
    try {
      appState.process = await getProcessState();
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
    appState.currentStep = hasGeneratedResults(appState) ? "results" : "process";
    appState.timelinePreviewOpen = false;
    appState.expandedDetailPanelIds = [];
    ensureFirstExpandedClip();
    syncAllClipsExpanded();
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
    const confirmed = await confirmWorkflowReset();
    if (!confirmed) {
      return;
    }

    try {
      await cleanGenerated();
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
    appState.expandedDetailPanelIds = [];
    appState.allClipsExpanded = false;
    appState.project = null;
    appState.reviewBusy = false;
    appState.exportPath = "";
    appState.exportBusy = false;
    appState.exportMessage = "";
    appState.timelinePreviewOpen = false;
    appState.resultsOrdering = "clip";
    appState.processLogsExpanded = false;
    clearPersistedMediaDir();
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
    if (!hasGeneratedResults(appState)) {
      return;
    }
    appState.currentStep = "results";
    ensureFirstExpandedClip();
    syncAllClipsExpanded();
    render();
  }

  async function handlePickMedia() {
    try {
      const selected = await pickMediaDirectory();
      console.log("[roughcut-stdio] media folder picker result:", selected);
      if (typeof selected === "string" && selected.trim()) {
        appState.mediaDir = selected;
        persistMediaDir(selected);
        appState.exportMessage = "";
        pushProcessLog(`Selected media folder: ${selected}`);
        await refreshMediaSummary();
        render();
      }
    } catch (error) {
      pushProcessLog(`Media folder selection failed: ${stringifyError(error)}`);
      render();
    }
  }

  async function handleStartProcess() {
    if (!appState.settings) {
      return;
    }

    await refreshRuntimeCheck();
    if (!appState.runtimeCheck?.bundled_runtime_ready || appState.runtimeCheck.bootstrap_required) {
      appState.currentStep = "choose";
      appState.process = {
        ...createInitialProcessState(),
        status: "blocked",
        logs: ["Runtime preparation is required before processing can start."],
      };
      render();
      return;
    }

    appState.currentStep = "process";
    appState.process = {
      ...createInitialProcessState(),
      running: true,
      status: "starting",
      logs: ["Starting process run..."],
    };
    render();

    try {
      await startProcess({
        mediaDir: appState.mediaDir,
        aiMode: appState.aiMode,
      });
      ensureProcessPolling();
    } catch (error) {
      appState.process.error = stringifyError(error);
      appState.process.running = false;
      appState.process.status = "failed";
      pushProcessLog(`Process failed to start: ${appState.process.error}`);
      render();
    }
  }

  function setAIMode(value: string) {
    appState.aiMode = value === "full" ? "full" : "fast";
    if (appState.settings) {
      appState.settings = {
        ...appState.settings,
        aiMode: appState.aiMode,
      };
    }
  }

  async function handleExportTimeline() {
    appState.exportBusy = true;
    appState.exportMessage = "";
    render();

    try {
      const targetPath = await chooseTimelineExportPath();
      if (!targetPath) {
        appState.exportBusy = false;
        render();
        return;
      }

      const exported = await exportTimeline(targetPath);
      appState.exportPath = exported;
      appState.exportMessage = `Exported Resolve timeline to ${exported}`;
    } catch (error) {
      appState.exportMessage = `Export failed: ${stringifyError(error)}`;
    } finally {
      appState.exportBusy = false;
      render();
    }
  }

  async function handleSetBestTake(assetId: string, segmentId: string) {
    appState.reviewBusy = true;
    appState.exportMessage = "";
    render();

    try {
      appState.project = await selectBestTake(assetId, segmentId);
      appState.exportMessage = "Updated the timeline with the editor-selected best take.";
      ensureFirstExpandedClip();
      syncAllClipsExpanded();
    } catch (error) {
      appState.exportMessage = `Best-take update failed: ${stringifyError(error)}`;
    } finally {
      appState.reviewBusy = false;
      render();
    }
  }

  async function handleClearBestTake(assetId: string) {
    appState.reviewBusy = true;
    appState.exportMessage = "";
    render();

    try {
      appState.project = await clearBestTake(assetId);
      appState.exportMessage = "Removed this clip's selected take from the timeline.";
      ensureFirstExpandedClip();
      syncAllClipsExpanded();
    } catch (error) {
      appState.exportMessage = `Best-take clear failed: ${stringifyError(error)}`;
    } finally {
      appState.reviewBusy = false;
      render();
    }
  }

  async function handleClearBestTakeOverride(assetId: string) {
    appState.reviewBusy = true;
    appState.exportMessage = "";
    render();

    try {
      appState.project = await clearBestTakeOverride(assetId);
      appState.exportMessage = "Restored analyzer-selected takes for this clip.";
      ensureFirstExpandedClip();
      syncAllClipsExpanded();
    } catch (error) {
      appState.exportMessage = `Best-take reset failed: ${stringifyError(error)}`;
    } finally {
      appState.reviewBusy = false;
      render();
    }
  }

  function toggleAllClips() {
    appState.allClipsExpanded = !appState.allClipsExpanded;
    if (appState.allClipsExpanded) {
      const project = appState.project?.project;
      if (project) {
        appState.expandedClipIds = resolveClipViews(project).map((view) => view.asset.id);
      }
    } else {
      appState.expandedClipIds = [];
    }
    render();
  }

  function setResultsOrdering(value: string) {
    appState.resultsOrdering = coerceResultsOrdering(value);
    if (appState.resultsOrdering === "clip") {
      ensureFirstExpandedClip();
      syncAllClipsExpanded();
    }
  }

  function toggleClip(clipId: string) {
    if (appState.expandedClipIds.includes(clipId)) {
      appState.expandedClipIds = appState.expandedClipIds.filter((value) => value !== clipId);
    } else {
      appState.expandedClipIds = [...appState.expandedClipIds, clipId];
    }
    syncAllClipsExpanded();
    render();
  }

  function toggleDetailPanel(panelId: string) {
    if (appState.expandedDetailPanelIds.includes(panelId)) {
      appState.expandedDetailPanelIds = appState.expandedDetailPanelIds.filter((value) => value !== panelId);
    } else {
      appState.expandedDetailPanelIds = [...appState.expandedDetailPanelIds, panelId];
    }
    render();
  }

  async function handleSaveSettings() {
    if (!appState.settingsDraft) {
      return;
    }

    appState.settingsBusy = true;
    appState.settingsMessage = "";
    render();

    try {
      const saved = await saveAppSettings(appState.settingsDraft);
      appState.settings = saved;
      appState.aiMode = saved.aiMode;
      appState.settingsDraft = { ...saved };
      appState.settingsBusy = false;
      appState.settingsMessage = "Saved runtime settings";
      await refreshRuntimeCheck();
      render();
    } catch (error) {
      appState.settingsBusy = false;
      appState.settingsMessage = `Save failed: ${stringifyError(error)}`;
      render();
    }
  }

  async function handlePrepareRuntime() {
    if (!appState.settings) {
      return;
    }

    appState.runtimeBusy = true;
    appState.runtimeMessage = "";
    render();

    try {
      const result = await runSetup(buildRuntimeConfig(appState.settings));
      appState.runtimeCheck = result;
      appState.runtimeMessage =
        result.runtime_ready && !result.bootstrap_required
          ? "Runtime preparation completed."
          : "Runtime preparation finished, but more setup is still required.";
    } catch (error) {
      appState.runtimeMessage = `Runtime preparation failed: ${stringifyError(error)}`;
    } finally {
      appState.runtimeBusy = false;
      render();
    }
  }

  async function handleApplyRuntimeFallback() {
    if (!appState.settings || !appState.runtimeCheck?.fallback_actions.length) {
      return;
    }

    const nextSettings = applyRuntimeFallback(appState.settings, appState.runtimeCheck.fallback_actions);
    appState.runtimeBusy = true;
    appState.runtimeMessage = "";
    render();

    try {
      const saved = await saveAppSettings(nextSettings);
      appState.settings = saved;
      appState.settingsDraft = appState.settingsOpen ? { ...saved } : appState.settingsDraft;
      appState.aiMode = saved.aiMode;
      await refreshRuntimeCheck();
      appState.runtimeMessage = `Fallback mode enabled: ${describeFallbackActions(appState.runtimeCheck?.fallback_actions ?? [])}`;
    } catch (error) {
      appState.runtimeBusy = false;
      appState.runtimeMessage = `Fallback update failed: ${stringifyError(error)}`;
      render();
    }
  }

  function ensureFirstExpandedClip() {
    if (!hasGeneratedResults(appState) || appState.expandedClipIds.length > 0) {
      return;
    }
    const firstAssetId = resolveClipViews(appState.project!.project)[0]?.asset.id;
    appState.expandedClipIds = firstAssetId ? [firstAssetId] : [];
  }

  function syncAllClipsExpanded() {
    const project = appState.project?.project;
    if (!project) {
      appState.allClipsExpanded = false;
      return;
    }

    const clipIds = resolveClipViews(project).map((view) => view.asset.id);
    appState.allClipsExpanded =
      clipIds.length > 0 && clipIds.every((clipId) => appState.expandedClipIds.includes(clipId));
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

  function isSettingsField(
    element: HTMLElement,
  ): element is HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
    return (
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLSelectElement
    ) && Boolean(element.dataset.settingsField);
  }

  function applySettingsField(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement) {
    if (!appState.settingsDraft) {
      return;
    }

    const field = element.dataset.settingsField as keyof AppSettings | undefined;
    if (!field) {
      return;
    }

    const value =
      element instanceof HTMLInputElement && element.type === "checkbox" ? element.checked : element.value;

    appState.settingsDraft = {
      ...appState.settingsDraft,
      [field]: coerceSettingsValue(field, value),
    };
  }
}

function coerceResultsOrdering(value: string): ResultsOrdering {
  return value === "score" ? "score" : "clip";
}

function coerceSettingsValue(field: keyof AppSettings, value: string | boolean) {
  if (typeof value === "boolean") {
    return value;
  }

  switch (field) {
    case "aiProvider":
      return value as AppSettings["aiProvider"];
    case "aiMode":
      return value === "full" ? "full" : "fast";
    case "transcriptProvider":
      return value as TranscriptProvider;
    default:
      return value;
  }
}

function buildRuntimeConfig(settings: AppSettings) {
  return {
    provider: settings.aiProvider,
    aiModel: settings.aiModel,
    aiBaseUrl: settings.aiBaseUrl,
    aiModelId: settings.aiModelId,
    aiModelRevision: "",
    aiModelCacheDir: "",
    aiDevice: settings.aiDevice,
    transcriptProvider: settings.transcriptProvider,
    transcriptModelSize: settings.transcriptModelSize,
    clipEnabled: settings.clipEnabled,
    projectName: settings.projectName,
    storyPrompt: settings.storyPrompt,
  };
}

function applyRuntimeFallback(settings: AppSettings, fallbackActions: string[]) {
  let nextSettings = { ...settings };

  for (const action of fallbackActions) {
    switch (action) {
      case "disable-transcript":
        nextSettings = { ...nextSettings, transcriptProvider: "disabled" };
        break;
      case "disable-clip":
        nextSettings = { ...nextSettings, clipEnabled: false };
        break;
      case "switch-provider-deterministic":
        nextSettings = { ...nextSettings, aiProvider: "deterministic" };
        break;
      default:
        break;
    }
  }

  return nextSettings;
}

function describeFallbackActions(fallbackActions: string[]) {
  if (!fallbackActions.length) {
    return "reduced-capability processing";
  }

  const labels = fallbackActions
    .map((action) => {
      switch (action) {
        case "disable-transcript":
          return "transcript disabled";
        case "disable-clip":
          return "CLIP scoring disabled";
        case "switch-provider-deterministic":
          return "AI provider switched to deterministic";
        default:
          return "";
      }
    })
    .filter((label) => label.length > 0);

  return labels.length ? labels.join(", ") : "reduced-capability processing";
}
