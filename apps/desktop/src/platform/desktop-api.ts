import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { confirm, open, save } from "@tauri-apps/plugin-dialog";

import type { AppSettings, LoadedProject, MediaFolderSummary, ProcessState } from "../app/types.ts";

export function listenProcessUpdate(onUpdate: (processState: ProcessState) => void) {
  return listen<ProcessState>("process-update", (event) => {
    onUpdate(event.payload);
  });
}

export function loadAppSettings() {
  return invoke<AppSettings>("load_app_settings");
}

export function saveAppSettings(settings: AppSettings) {
  return invoke<AppSettings>("save_app_settings", { settings });
}

export function getProcessState() {
  return invoke<ProcessState>("get_process_state");
}

export function loadActiveProject() {
  return invoke<LoadedProject>("load_active_project");
}

export function inspectMediaFolder(path: string) {
  return invoke<MediaFolderSummary>("inspect_media_folder", { path });
}

export function startProcess(request: { mediaDir: string; aiMode: string }) {
  return invoke("start_process", { request });
}

export function exportTimeline(targetPath: string) {
  return invoke<string>("export_timeline", { targetPath });
}

export function cleanGenerated() {
  return invoke("clean_generated");
}

export function pickMediaDirectory() {
  return open({
    directory: true,
    multiple: false,
    title: "Choose the media folder for Roughcut Stdio",
  });
}

export function chooseTimelineExportPath() {
  return save({
    title: "Export DaVinci Resolve Timeline",
    defaultPath: "roughcut-stdio.fcpxml",
  });
}

export function confirmWorkflowReset() {
  return confirm(
    "Go back to step 1 and reset the current desktop workflow state? This clears the selected folder and in-app results view, and deletes the generated folder.",
    {
      title: "Reset workflow",
      kind: "warning",
    },
  );
}
