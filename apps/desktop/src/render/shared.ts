import type { Step } from "../app/types.ts";
import { escapeHtml } from "../lib/html.ts";

export function renderMetric(label: string, value: string) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

export function renderStepChip(
  step: Step,
  number: string,
  label: string,
  currentStep: Step,
  completed: boolean,
) {
  const status = step === currentStep ? "current" : completed ? "done" : "";
  return `
    <article class="step-chip ${status}">
      <span class="step-index">${number}</span>
      <div>
        <strong>${label}</strong>
      </div>
    </article>
  `;
}
