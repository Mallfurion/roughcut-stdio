## Context

The current process output is technically complete but operationally noisy. The opening lines mix setup, configuration, and hard readiness failures into one flat stream, so a missing model or fallback condition can be skipped past as easily as an informational line. During analysis, the process emits routine per-asset lines that create a large scrolling transcript even when the operator mostly needs to know whether the run is advancing normally. At completion, the summary includes useful metrics, but it also includes low-signal bulk detail such as long source-only clip listings that drown out the actual outcome of the run.

There is an additional constraint: the process has two consumers with different needs. An interactive terminal benefits from color, segmented emphasis, and line replacement for progress. Persisted artifacts such as `generated/process-output.txt` and `generated/process-summary.txt` need plain, durable text that remains readable when opened later or displayed inside the desktop app. The design needs to improve the live operator experience without degrading saved artifacts or the desktop workflow.

## Goals / Non-Goals

**Goals:**
- Make setup and runtime readiness visible before processing begins.
- Give missing assets and misconfiguration a stronger visual treatment than ordinary informational output.
- Replace routine scrolling progress chatter with a compact single-line live progress view in interactive terminal runs.
- Shrink the default completion recap to the information an operator actually needs after a run.
- Preserve deterministic fallback and detailed persisted diagnostics even when the default terminal recap becomes more compact.

**Non-Goals:**
- Changing media discovery, scoring, AI targeting, or export behavior.
- Reducing the fidelity of persisted benchmark records.
- Replacing the desktop app's existing progress bar with terminal control sequences.
- Building a full interactive TUI beyond process output improvements.

## Decisions

### 1. Split process reporting into three explicit phases

Process output will be organized into:
- a preflight banner
- a live progress phase
- a compact completion summary

The preflight banner will present setup state before work starts. The live phase will focus on forward motion rather than preserving a line-by-line transcript of every asset. The completion summary will explain the run outcome in a compact, operator-focused way.

Rationale:
- The current output loses meaning because all status types share one presentation style.
- Operators need different information at startup, mid-run, and completion.

Alternatives considered:
- Keep a single flat stream and just tweak wording: rejected because the core problem is presentation structure, not only wording.
- Print larger headings around the existing output without changing flow: rejected because the per-asset spam and oversized recap would still dominate the experience.

### 2. Use severity-aware rendering with separate interactive and persisted sinks

The process should emit structured status events that include section and severity metadata rather than only raw strings. An interactive terminal renderer can then apply ANSI color and emphasis for `info`, `warn`, and `error` states, while persisted artifacts render the same events as plain text with readable severity labels and section headers.

Missing required model assets, broken runtime prerequisites, or unsupported configuration should render as high-severity output in interactive mode. Persisted files should remain plain-text and not depend on terminal capabilities.

Rationale:
- The operator needs visual distinction in live runs.
- Saved artifacts must remain portable and readable in editors, tests, and the desktop app log view.

Alternatives considered:
- Add ANSI color directly to all emitted strings: rejected because captured artifacts would contain control codes and become harder to read.
- Keep persisted and interactive output totally separate at the data level: rejected because it would duplicate reporting logic and increase drift risk.

### 3. Render single-line live progress only for interactive terminals

Interactive runs should replace routine per-asset logging with a single progress line updated in place using terminal control sequences. That line should show:
- processed / total assets
- current asset
- current stage or activity
- elapsed time
- ETA when available

Persisted output should not try to mirror every progress tick. Instead, it should record milestone events and the final summary so `generated/process-output.txt` remains readable and does not accumulate carriage-return artifacts.

Rationale:
- A live terminal benefits from motion without scroll spam.
- A saved file should preserve what happened, not every transient animation frame.

Alternatives considered:
- Write the same carriage-return updates into the persisted artifact: rejected because it produces unreadable logs.
- Remove routine progress output entirely and rely only on the desktop progress bar: rejected because terminal runs remain a supported workflow.

### 4. Make the completion recap concise by default and move bulk detail out of the operator path

The default completion recap should be limited to the categories that explain run outcome:
- workload summary
- effective runtime path
- key processed counts by path
- important fallback, degraded, or skipped paths
- headline timing and comparison context
- generated artifact locations

Bulky detail such as exhaustive source-only clip listings, long comparison-context dumps, or low-value counter enumerations should be removed from the default recap and preserved in detailed artifacts instead. Existing benchmark JSON should remain authoritative for full comparison context. Text artifacts such as `generated/process.log` can remain the place for expanded detail if needed.

Rationale:
- The operator should be able to understand the run outcome in seconds.
- Full detail is still useful, but it should not dominate the default recap.

Alternatives considered:
- Keep the current completion recap and only colorize it: rejected because the recap is too large even when styled.
- Drop detailed diagnostics entirely: rejected because debugging and benchmarking still need them.

### 5. Keep the change compatible with current desktop workflow consumers

The desktop process step already has its own progress bar and log area. This change should not force terminal control sequences into the desktop UI. Persisted process-output artifacts should therefore stay plain-text and milestone-oriented so the desktop "Show Logs" view remains readable. The structured event model can later support richer desktop presentation, but that is not required in this change.

Rationale:
- Terminal UX and desktop UX have different rendering constraints.
- The change should improve the shared process data shape rather than couple the desktop UI to terminal behavior.

Alternatives considered:
- Scope the change only to terminal scripts and ignore desktop consumers: rejected because the desktop log view already reads the same output artifacts.

## Risks / Trade-offs

- [Compact summaries may hide details some developers still want] -> Keep rich benchmark artifacts and detailed logs available outside the default recap.
- [ANSI styling may behave inconsistently across shells or redirected output] -> Enable color and line replacement only when stdout is an interactive TTY.
- [Progress percentages can imply precision even when assets vary widely in cost] -> Present the bar as asset-progress, not exact work-completion, and keep current-activity text visible.
- [Two output sinks can drift over time] -> Emit structured status events once and render them through separate formatters rather than maintaining parallel string logic.
- [Removing long detail blocks from the recap could affect existing manual workflows] -> Preserve detailed data in existing artifacts and verify the desktop log view still exposes enough context for follow-up investigation.

## Migration Plan

1. Introduce a structured process-reporting layer that can emit sectioned, severity-aware events.
2. Update process startup reporting to emit a preflight banner derived from current readiness/configuration checks.
3. Replace routine per-asset console chatter with interactive single-line progress rendering while keeping persisted milestone output readable.
4. Redesign the completion summary formatter to prioritize concise operator facts and artifact pointers.
5. Verify terminal runs, redirected output, generated artifacts, and desktop log rendering against healthy and degraded runtime scenarios.

## Open Questions

- Should the repository workflow expose an explicit verbose mode for developers who still want per-asset logging on demand?
- Should source-only clip detail remain in `generated/process.log`, or should it move to a dedicated diagnostics artifact if operators still need it occasionally?
- Should benchmark comparison context in the default recap be capped to the two or three most explanatory deltas, or should the cap be configurable?
