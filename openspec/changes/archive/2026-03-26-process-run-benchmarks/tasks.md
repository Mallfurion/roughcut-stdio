## 1. Benchmark Instrumentation

- [x] 1.1 Add a run-level benchmark data model for process runs, including run ID, timestamps, phase durations, workload counts, and effective runtime configuration
- [x] 1.2 Instrument the analyzer pipeline to emit structured timing for media discovery, per-asset analysis, take selection, and timeline assembly
- [x] 1.3 Persist detailed benchmark payloads under `generated/benchmarks/<run-id>/benchmark.json` and append a lightweight history entry to `generated/benchmarks/history.jsonl`

## 2. Process Output Persistence

- [x] 2.1 Update `scripts/process.sh` to write the exact terminal-facing process output to `generated/process-output.txt`
- [x] 2.2 Save a run-scoped copy of the terminal-facing output alongside the benchmark record for the completed run
- [x] 2.3 Extend the process summary to include current runtime totals and comparison deltas against prior benchmark history when available

## 3. Validation And Documentation

- [x] 3.1 Add or update tests for benchmark artifact creation and latest-run output persistence
- [x] 3.2 Document the new benchmark and process output artifacts in the process command and analyzer pipeline docs
- [x] 3.3 Validate the OpenSpec change
