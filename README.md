# Timeline Cutter

Timeline Cutter is now a desktop-first local Mac app for screening footage, surfacing the strongest visual segments, and exporting a Resolve-ready timeline.

## Quick Start

For a fresh clone on macOS, the intended flow is:

```bash
git clone <repo>
cd timeline-cutter
npm run setup
npm run view
```

After that, use the desktop app to:

1. choose media folder
2. process footage
3. review shortlisted shots
4. export a DaVinci Resolve timeline

## Product Flow

The intended user flow is:

1. run `npm run setup` before opening the app
2. choose media folder
3. process footage with visual progress
4. review shortlisted shots and grades
5. export a DaVinci Resolve timeline

The desktop interface lives in [apps/desktop](/Users/florin/Projects/personal/timeline-cutter/apps/desktop).

## Current Architecture

- `apps/desktop`
  - Tauri desktop shell
  - new guided UI written from scratch
  - native macOS file/save dialog integration
  - local command orchestration for process, review, and export
- `services/analyzer`
  - Python analysis and export engine
  - media discovery, prefiltering, shortlist construction, AI segment understanding, and `FCPXML` export
- `scripts`
  - shell entrypoints still used underneath by the desktop app

The browser app has been removed from the product surface. The analyzer and scripts remain the processing backend for the desktop app.

## Desktop Commands

Run the desktop app in development:

```bash
npm run dev:desktop
```

Build the desktop app:

```bash
npm run build:desktop
```

The old `view` entrypoint now opens the desktop app in development:

```bash
npm run view
```

## Backend Commands

These commands still exist because the desktop app orchestrates them internally and they are useful for debugging:

```bash
npm run setup
npm run check:ai
npm run process
npm run export
```

## Environment Variables

The repository still uses env vars for the analyzer runtime and media configuration. Configure those outside the app through `.env.local` or direct shell env vars. The desktop app is focused on media selection, processing, review, and export.

### Core

- `TIMELINE_MEDIA_DIR`
- `TIMELINE_PROJECT_NAME`
- `TIMELINE_STORY_PROMPT`
- `TIMELINE_PYTHON`

### AI Provider

- `TIMELINE_AI_PROVIDER`
  - `deterministic`
  - `lmstudio`
  - `mlx-vlm-local`
- `TIMELINE_AI_TIMEOUT_SEC`

### LM Studio

- `TIMELINE_AI_MODEL`
- `TIMELINE_AI_BASE_URL`

### MLX-VLM Local

- `TIMELINE_AI_MODEL_ID`
- `TIMELINE_AI_MODEL_REVISION`
- `TIMELINE_AI_MODEL_CACHE_DIR`
- `TIMELINE_AI_DEVICE`
- `TIMELINE_SKIP_MODEL_DOWNLOAD`

### AI Runtime Tuning

- `TIMELINE_AI_MODE`
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET`
- `TIMELINE_AI_MAX_KEYFRAMES`
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH`
- `TIMELINE_AI_CONCURRENCY`
- `TIMELINE_AI_CACHE`

See [.env.example](/Users/florin/Projects/personal/timeline-cutter/.env.example) for the current defaults.

## Recommended Local AI Config

Embedded Apple Silicon path:

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

External local server path:

```bash
TIMELINE_AI_PROVIDER=lmstudio
TIMELINE_AI_MODEL=qwen3.5-9b
TIMELINE_AI_BASE_URL=http://127.0.0.1:1234/v1
```

No-model path:

```bash
TIMELINE_AI_PROVIDER=deterministic
```

## Requirements

Required:

- Node.js
- npm
- Python 3.12+
- Xcode Command Line Tools on macOS
- Rust / Cargo for the Tauri desktop shell

For the useful local media-analysis path:

- `ffmpeg`
- optional `ffprobe`
- optional `PySceneDetect`
- optional `faster-whisper`

For `mlx-vlm-local`:

- `mlx`
- `mlx-vlm`
- `torch`
- `torchvision`
- `pillow`
- local prepared model files in `models/mlx-vlm`

The setup script now:

- runs `npm install`
- creates the Python environment
- installs `ffmpeg` automatically on macOS with Homebrew when possible
- checks for Xcode Command Line Tools
- installs Rust with Homebrew on macOS when possible
- installs the embedded MLX runtime requirements by default
- prepares the local MLX model cache

## Resolve Export

The analyzer exports `FCPXML` for DaVinci Resolve.

Backend export writes:

- [generated/timeline.fcpxml](/Users/florin/Projects/personal/timeline-cutter/generated/timeline.fcpxml)

The desktop app adds a native save flow on top of that backend export so the user can choose the final export destination visually.

## Verification

Python tests:

```bash
npm run test:python
```

Desktop app build:

```bash
npm run build:desktop
```

Note: this environment did not have Rust installed, so the Tauri shell could not be compiled here. The Python analyzer remains verified locally through the test suite.
