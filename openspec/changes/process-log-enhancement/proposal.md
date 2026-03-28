## Why

The current `npm run process` output makes critical setup state too easy to miss because readiness, warnings, and failures all appear in the same flat text stream. Once processing starts, per-asset line spam buries the useful signal, and the completion recap is large enough that the operator has to hunt for the few facts that actually explain what happened.

## What Changes

- Add a segmented preflight status banner at the start of process runs so media input, runtime readiness, model assets, and optional capabilities are shown as distinct sections instead of one undifferentiated block.
- Surface missing assets and misconfiguration with higher-severity terminal styling during interactive runs so issues like an unavailable MLX-VLM model are visually distinct from ordinary informational lines.
- Replace routine per-asset scrolling status lines with a single-line live progress presentation during interactive terminal runs, including processed count, current asset, active stage, elapsed time, and ETA.
- Reduce the completion recap to a compact operator summary that focuses on workload, effective runtime path, important fallback or skipped paths, benchmark timing, and artifact locations.
- Preserve detailed diagnostics and benchmark artifacts, but remove bulky default recap content such as exhaustive per-asset listings when that data is not required to understand the run outcome.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `processing-workflow`: Terminal-facing process reporting will become segmented, severity-aware, progress-compact, and more selective about what appears in the default completion recap.

## Impact

- `scripts/process.sh` process output orchestration
- `services/analyzer/app/analysis.py` runtime status and progress emission
- `services/analyzer/app/benchmarking.py` final summary formatting
- `services/analyzer/scripts/write_process_artifacts.py` persisted summary/log generation
- `apps/desktop/src/render/process-step.ts` and related workflow surfaces that display captured process logs
