## Why

`npm run process` currently produces only latest-run artifacts and a short terminal summary, which makes runtime regressions hard to spot and prior runs hard to compare. The workflow also does not persist the exact terminal-facing output shown by the process command, so the operator loses that context once the command exits.

## What Changes

- Add a run-level benchmark artifact set for the process/analyzer pipeline so each completed run records total elapsed time, major phase durations, workload counts, and effective runtime configuration.
- Persist benchmark history under `generated/benchmarks/` so the current run can be compared with earlier runs instead of only inspecting the latest `process.log`.
- Save the exact terminal-facing output emitted by `npm run process` into a file inside `generated/`, while also keeping a per-run copy alongside the benchmark record.
- Extend the process summary to include benchmark deltas against a prior run when history exists, while clearly surfacing comparison context such as media root, provider, and AI mode.
- Preserve the current latest-run convenience artifacts (`generated/project.json`, `generated/process.log`, `generated/process-summary.txt`) while adding benchmark-specific outputs rather than replacing them.

## Capabilities

### New Capabilities
- `process-benchmarking`: persistent benchmark records, run-to-run timing comparisons, and run-scoped benchmark artifacts for the process/analyzer pipeline.

### Modified Capabilities
- `processing-workflow`: process runs must persist the terminal-facing output in `generated/` and surface benchmark summaries as part of the normal process workflow.

## Impact

- Affected code:
  - `scripts/process.sh`
  - `services/analyzer/app/**` and `services/analyzer/scripts/scan_media_root.py` for phase timing instrumentation
  - any process-reporting helpers that shape summary output
- Affected outputs:
  - `generated/process-output.txt`
  - `generated/benchmarks/**`
  - `generated/process-summary.txt`
  - `generated/process.log`
- Affected docs:
  - process command and analyzer pipeline documentation
- Dependencies and systems:
  - existing local filesystem under `generated/`
  - current analyzer phase boundaries and runtime configuration inspection
