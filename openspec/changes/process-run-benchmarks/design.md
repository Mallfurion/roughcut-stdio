## Context

The current process workflow writes `generated/project.json`, `generated/process.log`, and `generated/process-summary.txt`, but those files represent only the latest run. The shell script prints a small operator-facing summary at the end of `npm run process`, yet that output is not preserved as a durable artifact. There is also no structured benchmark history for comparing total runtime or phase-level timing across runs.

The proposed change needs to improve observability without changing the local-first workflow, the existing analyzer outputs, or the deterministic fallback path. The benchmark system should remain file-based and repo-local so both terminal and desktop-driven runs can rely on the same artifacts.

## Goals / Non-Goals

**Goals:**
- Record a stable benchmark payload for each process run with total elapsed time, phase durations, workload counts, and effective runtime configuration.
- Persist benchmark history in `generated/` so the current run can be compared against previous runs without external infrastructure.
- Save the exact terminal-facing process output into a stable generated file for the latest run and a run-scoped file for historical inspection.
- Keep existing latest-run artifacts intact so current workflows and docs do not break.

**Non-Goals:**
- Building a separate benchmarking service, database, or dashboard.
- Replacing the existing `generated/project.json` and `generated/process.log` artifacts.
- Adding quality-evaluation benchmarks for segment ranking or editorial output in this change.
- Redesigning the desktop progress protocol beyond what is needed to consume the new generated artifacts later.

## Decisions

### 1. Store benchmarks in run-scoped directories under `generated/benchmarks/`

Each successful process run should receive a unique run ID and a dedicated directory such as `generated/benchmarks/<run-id>/`. That directory should hold the detailed benchmark JSON and a run-scoped copy of the terminal-facing output.

This keeps history append-only and avoids overwriting prior benchmark evidence. A root-only `generated/process-benchmark.json` file would be simpler, but it would lose run-to-run comparison value immediately.

### 2. Keep both latest-run convenience files and per-run historical files

The workflow should continue writing the current latest-run files in predictable locations:
- `generated/project.json`
- `generated/process.log`
- `generated/process-summary.txt`
- `generated/process-output.txt`

The benchmark subsystem should add per-run historical files rather than move the latest-run artifacts into a nested folder. This avoids breaking current operator habits, docs, and any desktop integration that expects the root `generated/` paths.

### 3. Split benchmark data into a detailed per-run payload and a lightweight history index

Each run directory should contain a structured benchmark payload with:
- run identifiers and timestamps
- total elapsed time
- major analyzer phase durations
- workload counts such as assets, candidate segments, deduplicated segments, and VLM targets
- effective provider/mode and other comparison-relevant configuration
- output file paths for the associated run artifacts

The root benchmark history should also keep an append-only summary index, such as `generated/benchmarks/history.jsonl`, so the next process run can quickly locate previous results without scanning and parsing every historical file.

This keeps comparisons cheap while still preserving full detail per run.

### 4. Capture comparison context explicitly instead of assuming all runs are directly comparable

Runtime comparisons become misleading if two runs differ materially in media root, asset count, AI provider, or AI mode. The benchmark record should therefore store those comparison dimensions and the process summary should surface them whenever the baseline run differs from the current run.

This is preferable to silently comparing unlike runs, which would produce runtime deltas that look precise but are operationally weak.

### 5. Instrument analyzer phase timing at the pipeline boundary, not by scraping terminal text

Total runtime can be measured in `scripts/process.sh`, but meaningful phase timing must come from the analyzer pipeline itself. The analyzer should emit or return structured phase-duration data for the major workflow boundaries already described in the docs: media discovery, per-asset analysis, take selection, and timeline assembly.

Using structured timing data avoids coupling benchmark generation to terminal formatting and keeps the saved process output focused on operator readability rather than machine parsing.

## Risks / Trade-offs

- Comparison drift across unlike runs -> Store media root, effective provider, AI mode, and workload counts in the benchmark record and show those differences in the comparison summary.
- History growth under `generated/benchmarks/` -> Keep the primary index lightweight and defer retention or pruning policy to a later change if the directory becomes too large.
- Instrumentation overhead -> Limit timing capture to major pipeline phases and summary counts rather than per-function tracing.
- Partial adoption between shell and analyzer layers -> Make the shell responsible for latest-run file persistence, while the analyzer owns only structured phase metrics.

## Migration Plan

1. Add benchmark artifact definitions and file paths to the process workflow and new benchmark capability specs.
2. Instrument analyzer phase timings and return them in a structured form that `scripts/process.sh` can persist.
3. Update `scripts/process.sh` to assign a run ID, write latest-run output files, create the per-run benchmark directory, and append to benchmark history.
4. Extend the process summary with comparison output against a prior benchmark when one exists.
5. Update command and pipeline documentation to describe the new generated artifacts.

## Open Questions

- Whether failed runs should also create benchmark records or whether the first version should scope history to completed runs only.
- Whether the comparison baseline should default to the immediately previous run or the most recent run with matching media root and effective AI configuration.
