import { hasGeneratedResults } from "../app/state.ts";
import type { AppState, Step } from "../app/types.ts";
import { renderChooseStep } from "./choose-step.ts";
import { renderProcessStep } from "./process-step.ts";
import { renderResultsStep } from "./results-step.ts";
import { renderSettingsDialog } from "./settings-dialog.ts";
import { renderStepChip } from "./shared.ts";

export function renderAppShell(appState: AppState) {
  return `
    <main class="shell">
      <section class="stepper card">
        <div class="stepper-layout">
          <button
            data-action="reset-workflow"
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
            ${renderStepChip("choose", "1", "Choose folder", appState.currentStep, stepCompleted(appState, "choose"))}
            ${renderStepChip("process", "2", "Process videos", appState.currentStep, stepCompleted(appState, "process"))}
            ${renderStepChip("results", "3", "View results", appState.currentStep, stepCompleted(appState, "results"))}
          </div>
          <button
            data-action="open-settings"
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

      ${renderCurrentStep(appState)}
      ${renderSettingsDialog(appState)}
    </main>
  `;
}

function renderCurrentStep(appState: AppState) {
  switch (appState.currentStep) {
    case "process":
      return renderProcessStep(appState, hasGeneratedResults(appState) && !appState.process.running);
    case "results":
      return renderResultsStep(appState);
    default:
      return renderChooseStep(appState);
  }
}

function stepCompleted(appState: AppState, step: Step) {
  if (step === "choose") {
    return Boolean(appState.mediaDir.trim());
  }
  if (step === "process") {
    return hasGeneratedResults(appState);
  }
  return false;
}
