# Commands Reference

## Setup & Verification

**Initial setup** (run once after cloning):

```bash
npm run setup
```

This installs dependencies, creates the Python environment, downloads tools (ffmpeg, etc.), and prepares the local MLX model cache if needed.

**Check AI availability**:

```bash
npm run check:ai
```

Verifies that required AI dependencies are installed and models are accessible.

---

## Desktop App

**Run in development** (with hot reload):

```bash
npm run dev:desktop
```

Opens the desktop app in development mode with browser DevTools available.

**Build for production**:

```bash
npm run build:desktop
```

Compiles the Tauri shell and packages the desktop app. Output is in `src-tauri/target/release/`.

**Quick launch** (same as dev):

```bash
npm run view
```

Launches the desktop app in development mode.

---

## Backend / Analyzer Commands

These commands process footage and generate output. They're called by the desktop app internally but can be run directly for debugging:

**Process footage**:

```bash
npm run process
```

Runs the complete analysis pipeline:
1. Media discovery
2. Per-asset analysis (signals, seed regions, deterministic refinement, assembly, optional semantic boundary validation, scoring)
3. Take selection
4. Timeline assembly

Generates:
- `generated/project.json` with all results
- `generated/process.log` with runtime/config diagnostics for the latest run
- `generated/process-summary.txt` with the latest operational and benchmark summary
- `generated/process-output.txt` with the exact terminal-facing output from the latest run
- `generated/benchmarks/history.jsonl` plus `generated/benchmarks/<run-id>/benchmark.json` for per-run benchmark history

**Export to DaVinci Resolve**:

```bash
npm run export
```

Generates `generated/timeline.fcpxml` from the processed project. Can be imported directly into DaVinci Resolve.

---

## Development & Testing

**Run Python tests**:

```bash
npm run test:python
```

Runs all unit tests in `services/analyzer/tests/` using unittest. Shows coverage and detailed output.

**Run specific test module**:

```bash
python3 -m unittest services.analyzer.tests.test_analysis -v
```

Run a single test module, class, or method for focused debugging.

**Validate OpenSpec dependency chaining**:

```bash
npm run check:openspec-graph
```

**Python linting**:

```bash
python3 -m pylint services/analyzer/app/*.py
```

Check code style and potential issues.

---

## Debugging Workflows

### Debug the analyzer step-by-step

Set `TIMELINE_AI_PROVIDER=deterministic` to skip VLM calls, then run:

```bash
TIMELINE_AI_PROVIDER=deterministic npm run process
```

This runs the full pipeline without multimodal model calls. The current segmentation stack is on by default; add `TIMELINE_SEGMENT_SEMANTIC_VALIDATION=false` if you want to isolate deterministic boundary behavior.

### Debug CLIP deduplication

Set media directory and enable CLIP:

```bash
TIMELINE_MEDIA_DIR=./media/test-clips TIMELINE_AI_CLIP_ENABLED=true npm run process
```

The dedup stats will be logged during the process step. Check `generated/project.json` to inspect `deduplicated` and `dedup_group_id` fields.

### Debug a specific asset

Modify the analyzer to add logging or breakpoints, then run:

```bash
npm run process 2>&1 | grep -A5 "asset-name"
```

Or run the Python analyzer directly with pdb:

```bash
python3 -m pdb services/analyzer/scripts/scan_media_root.py
```

### Inspect generated output

After processing, check the results:

```bash
# View project structure
cat generated/project.json | jq '.project | keys'

# View dedup statistics
cat generated/project.json | jq '.project.analysis_summary | {clip_dedup_group_count, clip_dedup_eliminated_count}'

# View all segments with dedup info
cat generated/project.json | jq '.assets[].segments[] | {id, deduplicated, dedup_group_id}'

# View the latest benchmark summary
cat generated/process-summary.txt

# View the latest terminal-facing process output
cat generated/process-output.txt

# View benchmark history
cat generated/benchmarks/history.jsonl
```

---

## Environment Variables for Testing

### Fast Mode (Deterministic + Quick Scoring)

```bash
TIMELINE_MEDIA_DIR=./media \
TIMELINE_AI_PROVIDER=deterministic \
TIMELINE_AI_MODE=fast \
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1 \
npm run process
```

Runs in seconds; good for testing pipeline logic without VLM.

### Full Analysis with CLIP

```bash
TIMELINE_MEDIA_DIR=./media \
TIMELINE_AI_PROVIDER=mlx-vlm-local \
TIMELINE_AI_CLIP_ENABLED=true \
TIMELINE_AI_MODE=full \
npm run process
```

Runs full analysis with CLIP deduplication and VLM understanding.

### Disable CLIP (Histogram Fallback)

```bash
TIMELINE_AI_CLIP_ENABLED=false \
TIMELINE_DEDUP_THRESHOLD=0.85 \
npm run process
```

Tests histogram-based deduplication when CLIP is unavailable.
