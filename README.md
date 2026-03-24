# Timeline Cutter

Timeline Cutter is structured around one simple flow:

1. `npm run setup`
2. `npm run process`
3. `npm run view`
4. `npm run export`

That is the intended interaction model for this repository.

If you are using `lmstudio` or `mlx-vlm-local`, run `npm run check:ai` before `process`.

If you want Resolve import paths to match a specific footage location, set `TIMELINE_MEDIA_DIR` to that exact folder path before running `process`.

## Configuration Overview

The repository is driven primarily by environment variables loaded from:

1. inline shell vars for a single command
2. `.env`
3. `.env.local`

The three main AI configurations are:

### Deterministic only

```bash
TIMELINE_AI_PROVIDER=deterministic
```

Use this when you want the fastest setup and no local model runtime.

### LM Studio backend

```bash
TIMELINE_AI_PROVIDER=lmstudio
TIMELINE_AI_MODEL=qwen3.5-9b
TIMELINE_AI_BASE_URL=http://127.0.0.1:1234/v1
```

Use this when you want an external local model server managed through LM Studio.

### Embedded MLX-VLM backend

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODEL_CACHE_DIR=./models/mlx-vlm
TIMELINE_AI_DEVICE=auto
```

Use this when you want the repo to own the local Apple-Silicon-optimized model runtime directly.

## Core Idea

- `setup` installs everything the repository needs locally
- `process` scans `TIMELINE_MEDIA_DIR` when set, otherwise the repository `media/` path, matches proxies when available, analyzes footage, and writes a generated timeline
- `view` starts the timeline selector web app against the latest generated timeline
- `export` writes a DaVinci Resolve `FCPXML` file from that generated timeline

The current analyzer has two layers:

- deterministic timeline selection
- optional Phase 1 AI segment understanding

That means AI can already describe and label segments, but it does not yet replace final best-take selection.

## Repository Paths

Important paths:

- `media/`
- `generated/project.json`
- `generated/timeline.fcpxml`
- `fixtures/sample-media/`
- `fixtures/sample-project.json`

Media root selection works like this:

1. `TIMELINE_MEDIA_DIR`, if set
2. `media/`, if the env var is not set

`media/` remains the default canonical footage location for this repository.

That path can be:

- a normal folder inside the repo
- a symbolic link pointing at footage stored somewhere else

This means you can do either of these:

```bash
mkdir media
```

or:

```bash
ln -s /absolute/path/to/your/footage media
```

By default, `npm run setup` creates `media` as a symlink to `fixtures/sample-media` if `media` does not already exist. That gives you a working demo flow immediately.

If you want to pin the media path through an environment variable, either run commands like this:

```bash
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage npm run process
```

or create a local env file:

```bash
cp .env.example .env.local
```

Then edit `.env.local` and set:

```bash
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage
```

## Prerequisites

Required:

- `Node.js 24+`
- `npm 11+`
- `Python 3.12+`

Optional but recommended for real footage analysis:

- `ffmpeg`
- `ffprobe`
- `PySceneDetect`
- `faster-whisper`
- `LM Studio` for local multimodal analysis, or the Python runtime dependencies for `mlx-vlm-local`

Optional for the analyzer API:

- `FastAPI`
- `uvicorn`

Notes:

- on macOS with Homebrew, `npm run setup` will install `ffmpeg` automatically if it is missing
- the pipeline still runs without those optional media tools
- when they are missing, the analyzer uses deterministic fallbacks
- silent b-roll workflows remain testable even without speech tooling
- clips without proxies are supported and processed as source-only media
- both `lmstudio` and `mlx-vlm-local` are optional; if the configured AI backend is unavailable, Phase 1 AI analysis falls back to deterministic structured output

## The Main Flow

### 1. Setup

Run:

```bash
npm run setup
```

What it does:

- runs `npm install`
- creates `.venv`
- creates `generated/`
- installs `ffmpeg` automatically on macOS when Homebrew is available and `ffmpeg` is missing
- creates `media -> fixtures/sample-media` if `media` does not already exist and `TIMELINE_MEDIA_DIR` is not set

After setup, the next command is:

```bash
npm run process
```

If you configured a non-deterministic AI backend, you can validate it first with:

```bash
npm run check:ai
```

That command:

- loads `.env` and `.env.local`
- inspects the configured AI provider
- validates LM Studio reachability when `TIMELINE_AI_PROVIDER=lmstudio`
- validates local model readiness when `TIMELINE_AI_PROVIDER=mlx-vlm-local`
- exits with a non-zero status if the configured non-deterministic provider is unavailable

### 2. Process

Run:

```bash
npm run process
```

What it does:

- reads footage from `TIMELINE_MEDIA_DIR` when set, otherwise from `media/`
- discovers candidate video files
- classifies source clips and proxy clips
- matches proxies to sources
- keeps source-only clips when no matching proxy exists
- samples frames and runs a cheap visual prefilter before any VLM call
- generates candidate segments
- shortlists only the strongest candidate regions per asset for VLM refinement
- builds evidence bundles for each segment
- runs Phase 1 AI understanding when configured
- falls back to deterministic structured analysis when no AI provider is available
- scores silent and spoken footage
- builds a timeline
- writes the result to `generated/project.json`

Output files:

- `generated/project.json`
- `generated/process.log`
- `generated/process-summary.txt`
- `generated/analysis/` for extracted keyframes, contact sheets, and cached AI artifacts when `ffmpeg` is available and the AI provider requires them

During processing, the CLI now reports:

- media root being scanned
- AI provider configuration
- whether the configured AI backend is ready
- whether the run is using the configured backend or falling back to deterministic analysis
- AI runtime mode, shortlist size, keyframe count, width, concurrency, and cache status
- discovered video file count
- matched source asset count
- how many frames were sampled by the prefilter stage
- how many segments were shortlisted before the VLM stage
- how many segments actually reached the VLM stage
- how many segments were analyzed live by the configured AI backend
- how many segments were served from AI cache
- how many segments fell back after an AI backend failure
- how many segments were skipped before VLM in fast mode
- a per-asset progress bar with elapsed time and estimated time remaining

You can customize the processing prompt with environment variables:

```bash
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage \
TIMELINE_PROJECT_NAME="Weekend Edit" \
TIMELINE_STORY_PROMPT="Build a cinematic sequence with a strong opener and a calm outro." \
npm run process
```

### Optional AI Configuration

The analyzer can call a local model through either `lmstudio` or `mlx-vlm-local` during `process`.

Add this to `.env.local`:

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODEL_REVISION=
TIMELINE_AI_MODEL_CACHE_DIR=./models/mlx-vlm
TIMELINE_AI_DEVICE=auto
TIMELINE_AI_TIMEOUT_SEC=45
TIMELINE_AI_MODE=fast
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1
TIMELINE_AI_MAX_KEYFRAMES=1
TIMELINE_AI_KEYFRAME_MAX_WIDTH=448
TIMELINE_AI_CONCURRENCY=2
TIMELINE_AI_CACHE=true
```

Recommended local model:

- `mlx-community/Qwen3.5-0.8B-4bit` via `mlx-vlm-local`
- or a smaller vision model exposed through `lmstudio`

For `mlx-vlm-local`:

1. set `TIMELINE_AI_PROVIDER=mlx-vlm-local`
2. run `npm run setup`
3. the setup script installs the optional Python dependencies, including `mlx`, `mlx-vlm`, `torch`, and `torchvision`, and downloads the configured model into the local MLX cache unless `TIMELINE_SKIP_MODEL_DOWNLOAD=1`
4. on macOS with Homebrew, setup also installs `ffmpeg` automatically if needed
5. on other systems, install `ffmpeg` manually before running `npm run check:ai`
6. run `npm run check:ai`
7. `mlx-vlm-local` is intended for Apple Silicon; `TIMELINE_AI_DEVICE=auto` resolves to the Metal-backed MLX runtime and `cpu` is only for debugging

Expected LM Studio setup:

1. download and load the model in LM Studio
2. enable the local OpenAI-compatible server
3. keep it available at `http://127.0.0.1:1234/v1`

If the configured AI backend is not ready, `process` still succeeds and falls back to deterministic structured analysis.
For `mlx-vlm-local`, normal `process` runs are expected to reuse the prepared local model files from setup instead of hitting the remote model hub again.

## Configuration Reference

These are the main environment variables the repository supports.

### Footage And Project

- `TIMELINE_MEDIA_DIR`
  - Absolute or repo-relative path to the footage root used by `process`.
  - If unset, the repo uses `media/`.
- `TIMELINE_PROJECT_NAME`
  - Project name written into `generated/project.json`.
- `TIMELINE_STORY_PROMPT`
  - High-level editing brief passed into the analyzer and AI layer.

### AI Provider Selection

- `TIMELINE_AI_PROVIDER`
  - One of: `deterministic`, `lmstudio`, `mlx-vlm-local`
  - `deterministic` disables model inference and uses rule-based structured output only.
  - `lmstudio` uses the OpenAI-compatible HTTP API exposed by LM Studio.
  - `mlx-vlm-local` uses the embedded MLX-VLM runtime.
- `TIMELINE_AI_TIMEOUT_SEC`
  - Request or inference timeout used by the provider path.

### LM Studio Settings

- `TIMELINE_AI_MODEL`
  - Model name exposed by LM Studio.
- `TIMELINE_AI_BASE_URL`
  - LM Studio OpenAI-compatible endpoint, normally `http://127.0.0.1:1234/v1`.

### MLX-VLM Local Settings

- `TIMELINE_AI_MODEL_ID`
  - Hugging Face model id for the embedded MLX-VLM backend.
  - Default documented value: `mlx-community/Qwen3.5-0.8B-4bit`
- `TIMELINE_AI_MODEL_REVISION`
  - Optional pinned model revision.
- `TIMELINE_AI_MODEL_CACHE_DIR`
  - Local cache directory where model artifacts are stored.
- `TIMELINE_AI_DEVICE`
  - One of: `auto`, `metal`, `mps`, `gpu`, `cpu`
  - For `mlx-vlm-local`, `auto`, `metal`, `mps`, and `gpu` all resolve to the Metal-backed MLX runtime.
- `TIMELINE_SKIP_MODEL_DOWNLOAD`
  - `0` or `1`
  - Only used during `npm run setup`
  - `1` skips the MLX-VLM bootstrap/download step.

### AI Runtime Tuning

- `TIMELINE_AI_MODE`
  - `fast` or `full`
  - `fast` is the default and is the recommended mode for normal use.
  - `full` is slower and sends more segments to the AI layer.
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET`
  - Maximum shortlisted candidate segments per source asset that can reach the AI stage.
- `TIMELINE_AI_MAX_KEYFRAMES`
  - Number of keyframes extracted per shortlisted segment before contact-sheet generation.
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH`
  - Maximum width for extracted keyframes before they are stitched or sent to the provider path.
- `TIMELINE_AI_CONCURRENCY`
  - Bounded concurrency used for AI-stage work where applicable.
- `TIMELINE_AI_CACHE`
  - `true` or `false`
  - Enables on-disk reuse of AI outputs across reruns.

### Setup

- `TIMELINE_PYTHON`
  - Optional explicit Python interpreter path for `npm run setup`.

## Recommended Configurations

### Fastest setup

```bash
TIMELINE_AI_PROVIDER=deterministic
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage
```

### Recommended self-contained local AI

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODEL_CACHE_DIR=./models/mlx-vlm
TIMELINE_AI_DEVICE=auto
TIMELINE_AI_MODE=fast
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1
TIMELINE_AI_MAX_KEYFRAMES=1
TIMELINE_AI_KEYFRAME_MAX_WIDTH=448
TIMELINE_AI_CACHE=true
```

### Recommended LM Studio setup

```bash
TIMELINE_AI_PROVIDER=lmstudio
TIMELINE_AI_MODEL=qwen3.5-9b
TIMELINE_AI_BASE_URL=http://127.0.0.1:1234/v1
TIMELINE_AI_MODE=fast
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1
TIMELINE_AI_MAX_KEYFRAMES=1
TIMELINE_AI_KEYFRAME_MAX_WIDTH=448
TIMELINE_AI_CACHE=true
```

### Fast AI Mode

The default AI mode is `fast`.

That mode is designed to keep local-model processing practical:

- only the top shortlisted segments per asset go through the configured AI backend
- non-shortlisted segments still receive deterministic structured analysis
- a cheap sampled-frame prefilter runs before any VLM analysis
- shortlisted segments are sent as stitched contact sheets instead of multiple loose images
- `lmstudio` is called once per asset shortlist instead of once per segment whenever possible
- `mlx-vlm-local` runs in-process against shortlisted contact-sheet images on Apple Silicon
- only a very small number of downscaled keyframes are sent
- AI results are cached on disk
- a small bounded concurrency is used instead of fully serial processing

Relevant settings:

- `TIMELINE_AI_MODE=fast|full`
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET`
- `TIMELINE_AI_MAX_KEYFRAMES`
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH`
- `TIMELINE_AI_CONCURRENCY`
- `TIMELINE_AI_CACHE=true|false`

Recommended local defaults:

- `TIMELINE_AI_MODE=fast`
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1`
- `TIMELINE_AI_MAX_KEYFRAMES=1`
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH=448`
- `TIMELINE_AI_CONCURRENCY=2`
- `TIMELINE_AI_CACHE=true`

Use `TIMELINE_AI_MODE=full` only when you explicitly want full per-segment analysis and are willing to wait longer.

You can check connectivity without running a full analysis:

```bash
npm run check:ai
```

Example successful output:

```text
configured_provider: lmstudio
effective_provider: lmstudio
model: qwen3.5-9b
revision: (none)
cache_dir: (none)
device: auto
base_url: http://127.0.0.1:1234/v1
available: yes
detail: LM Studio is reachable at http://127.0.0.1:1234/v1; model 'qwen3.5-9b' will be used.
```

Example `mlx-vlm-local` failure output before setup:

```text
configured_provider: mlx-vlm-local
effective_provider: deterministic
model: mlx-community/Qwen3.5-0.8B-4bit
revision: (none)
cache_dir: /absolute/path/to/repo/models/mlx-vlm
device: auto
base_url: http://127.0.0.1:1234/v1
available: no
detail: MLX-VLM local backend is not ready because required Python modules are missing: mlx, mlx-vlm, torch, torchvision, pillow. Falling back to deterministic analysis.
```

After processing, the next command is:

```bash
npm run view
```

### 3. View

Run:

```bash
npm run view
```

What it does:

- starts the Next.js timeline selector app
- loads `generated/project.json` if it exists
- falls back to `fixtures/sample-project.json` if nothing has been processed yet
- shows Phase 1 AI fields such as provider, keep label, confidence, roles, rationale, and evidence coverage when present

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://localhost:3000/api/project](http://localhost:3000/api/project)
- [http://localhost:3000/api/export/fcpxml](http://localhost:3000/api/export/fcpxml)

After review, the final command is:

```bash
npm run export
```

### 4. Export

Run:

```bash
npm run export
```

What it does:

- reads `generated/project.json`
- exports a DaVinci Resolve compatible `FCPXML`
- writes the result to `generated/timeline.fcpxml`

Output file:

- `generated/timeline.fcpxml`

You can then import that XML into DaVinci Resolve and validate clip order, trims, and relinking behavior.

## Simple End-To-End Demo

If you want the shortest possible test flow:

```bash
npm run setup
npm run process
npm run view
```

Then, in another terminal:

```bash
npm run export
```

This works immediately because `setup` points `media/` at the synthetic demo footage unless you already provided your own `media` path.

To test the AI layer with fixture media:

```bash
TIMELINE_MEDIA_DIR=fixtures/sample-media \
TIMELINE_AI_PROVIDER=mlx-vlm-local \
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit \
npm run process

npm run view
```

Then inspect:

- [http://localhost:3000](http://localhost:3000)
- [generated/project.json](/Users/florin/Projects/personal/timeline-cutter/generated/project.json)

In `generated/project.json`, each `candidate_segment` should contain:

- `evidence_bundle`
- `ai_understanding`

If `lmstudio` is active, `ai_understanding.provider` should be `lmstudio`. If `mlx-vlm-local` is active, it should be `mlx-vlm-local`.

If not, it will usually be `deterministic`.

## Using Your Own Footage

Preferred for real Resolve workflows: set `TIMELINE_MEDIA_DIR` to the exact folder path you want the generated timeline to reference.

Inline:

```bash
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage npm run process
```

Persistent local config:

```bash
cp .env.example .env.local
```

Then set:

```bash
TIMELINE_MEDIA_DIR=/absolute/path/to/your/footage
```

Fallback option: replace the default `media` symlink with your own footage location:

```bash
rm media
ln -s /absolute/path/to/your/footage media
```

Recommended structure:

```text
your-footage/
  Originals/
  Proxy/
```

No-proxy workflows are also supported:

```text
your-footage/
  DJI_0692.MP4
  DJI_0693.MP4
  A001_08101522_C001.mov
```

If no proxy exists for a clip:

- the clip is still processed
- the original file is used as the analysis reference
- the original file is used as the export reference
- `generated/process-summary.txt` lists it as `source-only`
- Resolve must be able to access that original file path when you import the XML

Proxy detection currently uses:

- directory names like `Proxy`, `Proxies`, `Optimized Media`
- filename markers like `proxy`, `prox`, `optimized`

Then rerun:

```bash
npm run process
npm run view
npm run export
```

## What `process` Uses Internally

If installed locally:

- `ffprobe` for media metadata
- `PySceneDetect` for scene boundaries
- `faster-whisper` for transcript excerpts
- `ffmpeg` for keyframe extraction
- `lmstudio` or `mlx-vlm-local` for local multimodal segment understanding

If not installed:

- metadata defaults are used
- deterministic segment windows are used
- transcript excerpts remain empty

That means:

- spoken clips work better with the optional tools installed
- silent b-roll still works without them
- source-only clips still participate in the timeline when no proxy is available
- AI segment descriptions and labels are available now
- final take selection is still deterministic until the next phase

## Phase 1 AI Output

Phase 1 adds structured per-segment analysis but does not yet change the final take-selection logic.

Each segment can now include:

- evidence bundle
- AI summary
- provider name
- keep / maybe / reject label
- confidence
- proposed story roles
- rationale
- risk flags

This is meant to let you inspect and trust the AI layer before it starts deciding selections automatically.

## Optional Manual Commands

The repository is now centered on npm scripts, but these lower-level commands still exist if you want to inspect the internals.

Run tests:

```bash
npm run test:python
```

Scan manually:

```bash
python3 services/analyzer/scripts/scan_media_root.py "Fixture Scan" media "Build a visual-first rough cut."
```

Export manually:

```bash
python3 services/analyzer/scripts/export_fcpxml.py generated/project.json > generated/timeline.fcpxml
```

Build the web app:

```bash
npm run build:web
```

## Optional Analyzer API

If you want the FastAPI server directly:

```bash
source .venv/bin/activate
python3 -m pip install -e './services/analyzer[api]'
```

Then run:

```bash
source .venv/bin/activate
uvicorn services.analyzer.app.main:app --reload
```

Useful endpoints:

- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- [http://127.0.0.1:8000/capabilities](http://127.0.0.1:8000/capabilities)
- [http://127.0.0.1:8000/projects/sample](http://127.0.0.1:8000/projects/sample)
- [http://127.0.0.1:8000/projects/sample/export/fcpxml](http://127.0.0.1:8000/projects/sample/export/fcpxml)

## Testing Checklist

The intended test sequence is:

1. `npm run setup`
2. `npm run process`
3. `npm run view`
4. `npm run export`

Expected results:

- `generated/project.json` exists after `process`
- `generated/process-summary.txt` tells you how many clips are proxy-backed vs source-only
- the browser app shows a generated timeline after `view`
- `generated/timeline.fcpxml` exists after `export`

## Troubleshooting

### `npm run setup` fails during Python install

Make sure `python3` points to Python 3.12+.

Check:

```bash
python3 --version
```

### `npm run process` says `media` is missing

Run:

```bash
npm run setup
```

or create the symlink yourself:

```bash
ln -s /absolute/path/to/your/footage media
```

### `npm run process` completes but the timeline is weak

That usually means the optional media tooling is not installed, so the pipeline is using fallbacks.

Install:

```bash
brew install ffmpeg
source .venv/bin/activate
python3 -m pip install scenedetect faster-whisper
```

Then rerun:

```bash
npm run process
```

### `npm run export` fails

Make sure `generated/project.json` exists first.

Run:

```bash
npm run process
```

### The web app still shows sample data

That means `generated/project.json` does not exist yet. Run:

```bash
npm run process
```

## Main Commands

```bash
npm run setup
npm run process
npm run view
npm run export
```
