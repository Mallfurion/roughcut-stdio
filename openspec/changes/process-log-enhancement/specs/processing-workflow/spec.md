## ADDED Requirements

### Requirement: Process SHALL present preflight runtime status prominently
Before asset analysis begins, the process workflow SHALL present a segmented preflight status block that distinguishes input configuration, runtime readiness, model-asset readiness, and optional capability status. Missing required assets or runtime misconfiguration SHALL be rendered as higher-severity operator output than ordinary informational lines.

#### Scenario: Required model asset is missing at startup
- **WHEN** `npm run process` starts with a configured runtime that depends on missing local model assets
- **THEN** terminal-facing output SHALL present that condition in a distinct high-severity preflight status section before asset analysis begins
- **THEN** the output SHALL state the effective fallback path or blocked condition rather than burying it among ordinary configuration lines

#### Scenario: Process run starts with healthy local runtime prerequisites
- **WHEN** `npm run process` starts and required local runtime prerequisites are available
- **THEN** terminal-facing output SHALL group startup information into named preflight sections
- **THEN** those sections SHALL make ready informational state visually distinguishable from warnings or errors

### Requirement: Process SHALL render compact live progress for interactive runs
When the process workflow is attached to an interactive terminal, it SHALL present routine progress as a single in-place live progress line rather than appending routine per-asset progress lines for every analyzed asset. Persisted text artifacts for the run SHALL remain readable plain text and SHALL not rely on carriage-return animation frames to preserve progress meaning.

#### Scenario: Interactive terminal run processes many assets
- **WHEN** `npm run process` is attached to an interactive terminal and processes multiple assets
- **THEN** the operator SHALL see a live progress line that updates in place with processed count, total count, current asset, and active processing context
- **THEN** routine progress updates SHALL not append a new scrolling line for each processed asset

#### Scenario: Persisted process output is written for the same run
- **WHEN** the run also writes `generated/process-output.txt`
- **THEN** that artifact SHALL preserve readable milestone-oriented progress text
- **THEN** it SHALL not contain raw terminal control sequences that depend on in-place line replacement

## MODIFIED Requirements

### Requirement: Process SHALL report operational status during long runs
The process workflow SHALL report operator-facing status in a segmented start/progress/end structure while continuing to preserve benchmark timing statistics and key workload counters. This reporting SHALL be included in `generated/process-summary.txt`, in the terminal-facing output saved to `generated/process-output.txt`, and in the benchmark artifacts for the completed run. The default completion recap SHALL prioritize concise operator-relevant information over exhaustive per-asset listings.

#### Scenario: Process run has benchmark history available
- **WHEN** `npm run process` completes and at least one prior benchmark record exists
- **THEN** the process summary SHALL report the current run's total elapsed time
- **THEN** the process summary SHALL report at least one prior-run comparison for that elapsed time
- **THEN** the terminal-facing output saved for the run SHALL include the same benchmark summary shown to the operator

#### Scenario: Process run has no benchmark history available
- **WHEN** `npm run process` completes and no prior benchmark record exists
- **THEN** the process summary SHALL still report the current run's total elapsed time
- **THEN** the process summary SHALL indicate that no prior benchmark is available for comparison
- **THEN** the absence of benchmark history SHALL not cause a warning or failure

#### Scenario: Completed run emits compact operator recap
- **WHEN** `npm run process` completes successfully
- **THEN** the default completion recap SHALL report asset and segment workload, effective runtime path, important fallback or skipped-path counts, headline timing, and artifact locations
- **THEN** the default completion recap SHALL not dump exhaustive per-asset diagnostic listings unless the operator explicitly opts into a more verbose path

### Requirement: Process SHALL preserve explicit degraded-runtime reporting
The process workflow SHALL preserve explicit status for degraded or fallback runtime behavior rather than only reporting successful activation paths. Terminal-facing process output and generated process artifacts SHALL distinguish unavailable optional paths from intentionally skipped or budget-gated paths, and SHALL surface that distinction clearly in both startup and completion reporting.

#### Scenario: Optional runtime path is unavailable
- **WHEN** a configured optional runtime path cannot be used during processing
- **THEN** generated process artifacts SHALL preserve a named degraded or fallback status for that path
- **THEN** processing SHALL continue when deterministic fallback is supported
- **THEN** startup and completion reporting SHALL present that unavailable state as distinct from ordinary informational output

#### Scenario: Optional runtime path is skipped by gating
- **WHEN** the analyzer intentionally skips an expensive optional path because of gating, budget, or readiness rules
- **THEN** generated process artifacts SHALL preserve that skip or gating reason
- **THEN** the skip SHALL remain distinguishable from a hard failure
- **THEN** the default completion recap SHALL describe that path as intentionally skipped rather than unavailable
