# Roughcut Stdio

A local-first AI-assisted footage screening and rough-cut tool for video editors.

## What This Does

There is too much footage to watch manually. **Roughcut Stdio** solves this by:

- **Scanning** a large set of videos to find candidate moments
- **Surfacing** the strongest visual segments using AI analysis
- **Grading** each segment on visual qualities like subject, motion, composition, and interest
- **Assembling** those selections into a first-pass rough timeline

The goal is to help editors skip raw footage scrubbing and move directly from media ingestion to usable shot selection.

📖 **Read the full vision:** [docs/manifesto.md](docs/manifesto.md)

## Quick Start

For a fresh clone on macOS:

```bash
git clone <repo>
cd roughcut-stdio
npm run setup
npm run view
```

Then use the desktop app to:

1. Choose a media folder
2. Process footage (the analyzer scans and screens the videos)
3. Review shortlisted shots and their grades
4. Export a DaVinci Resolve timeline

## How It Works

The analyzer runs in four phases:

1. **Media Discovery** — Find all video files and match sources to proxies
2. **Per-Asset Analysis** — Extract signals, build candidate segments, score them, run AI analysis
3. **Take Selection** — Score all candidates and pick the best segments per asset
4. **Timeline Assembly** — Order selected takes into a rough cut

📖 **Detailed walkthrough:** [docs/analyzer-pipeline.md](docs/analyzer-pipeline.md)

## Architecture

The project is split into three layers:

**Frontend** — `apps/desktop/`

- Native macOS Tauri desktop app
- File dialog integration and media selection
- Processing progress display
- Timeline review and export interface

**Backend** — `services/analyzer/` (Python)

- Media discovery and proxy matching
- Frame and audio signal extraction
- Scene detection and candidate segment building
- Prefilter scoring and shortlist selection
- Evidence building (keyframe/contact sheet extraction)
- CLIP semantic scoring and deduplication
- VLM analysis (vision-language model understanding)
- FCPXML export for DaVinci Resolve

**Scripts** — `scripts/`

- Shell entrypoints for setup, processing, and export
- Called by the desktop app or used directly for debugging

The browser-based review interface has been replaced by the native desktop app. The analyzer remains the core processing engine.

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

## Configuration

The analyzer is configured through environment variables, typically set in `.env.local`:

### Media & Project

- `TIMELINE_MEDIA_DIR` — Root directory to scan for video files
- `TIMELINE_PROJECT_NAME` — Name for the project and output files
- `TIMELINE_STORY_PROMPT` — Optional narrative goal passed to VLM as context
- `TIMELINE_PYTHON` — Path to Python executable (auto-detected if not set)

### AI Provider Selection

- `TIMELINE_AI_PROVIDER` — One of: `deterministic`, `lmstudio`, `mlx-vlm-local` (default: `deterministic`)
- `TIMELINE_AI_TIMEOUT_SEC` — Timeout for VLM requests

### CLIP Semantic Scoring

- `TIMELINE_AI_CLIP_ENABLED` — Enable CLIP embedding-based semantic scoring (default: `true`)
- `TIMELINE_AI_CLIP_MIN_SCORE` — Score threshold for CLIP-gating [0–1] (default: `0.35`)
- `TIMELINE_DEDUP_THRESHOLD` — Histogram similarity threshold for dedup when CLIP unavailable (default: `0.85`)

### VLM Provider: LM Studio

- `TIMELINE_AI_MODEL` — Model name (e.g., `qwen3.5-9b`)
- `TIMELINE_AI_BASE_URL` — Server URL (e.g., `http://127.0.0.1:1234/v1`)

### VLM Provider: MLX-VLM Local

- `TIMELINE_AI_MODEL_ID` — Model identifier from HuggingFace
- `TIMELINE_AI_MODEL_REVISION` — Model revision/version tag
- `TIMELINE_AI_MODEL_CACHE_DIR` — Cache directory for model weights
- `TIMELINE_AI_DEVICE` — Device to run on (`auto`, `cpu`, `gpu`)
- `TIMELINE_SKIP_MODEL_DOWNLOAD` — Skip auto-download if weights already cached

### Runtime Tuning

- `TIMELINE_AI_MODE` — `fast` or `full` (default: `fast`); limits VLM targets per asset in fast mode
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` — Max VLM targets per asset in fast mode (default: `3`)
- `TIMELINE_AI_MAX_KEYFRAMES` — Keyframes to extract per segment (default: `3`)
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH` — Max width for keyframe/contact sheet (default: `720`)
- `TIMELINE_AI_CONCURRENCY` — Parallel VLM requests (default: `2`)
- `TIMELINE_AI_CACHE` — Cache VLM responses across runs (default: `true`)

📖 **Full configuration guide:** [docs/analyzer-pipeline.md#configuration](docs/analyzer-pipeline.md#configuration)

See [.env.example](.env.example) for the current defaults.

## Getting Started With AI

### Fastest: Deterministic (No Model)

Requires no AI setup. Uses only visual quality metrics:

```bash
TIMELINE_AI_PROVIDER=deterministic
```

### Recommended: MLX-VLM Local (Apple Silicon)

Fast inference on Mac using embedded MLX runtime:

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODE=fast
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1
```

The setup script installs MLX and model weights automatically.

### Alternative: LM Studio Server

Run a local LM Studio server, then point the analyzer to it:

```bash
TIMELINE_AI_PROVIDER=lmstudio
TIMELINE_AI_MODEL=qwen3.5-9b
TIMELINE_AI_BASE_URL=http://127.0.0.1:1234/v1
```

## Requirements

### Always Required

- Node.js 18+
- npm 9+
- Python 3.12+
- Xcode Command Line Tools (macOS)
- Rust / Cargo (for Tauri desktop shell)

### For Media Analysis

Installed automatically by `npm run setup`:

- `ffmpeg` — Frame/audio extraction
- `ffprobe` — Optional; metadata probing
- `PySceneDetect` — Optional; improved scene detection
- `faster-whisper` — Optional; speech transcription

### For MLX-VLM Local (Optional)

The setup script installs these automatically if you choose the MLX provider:

- `mlx` — Apple Silicon ML framework
- `mlx-vlm` — Vision-language model runtime
- `torch`, `torchvision`, `pillow` — Model dependencies

The setup script automates most of this. Run `npm run setup` and follow the prompts.

## DaVinci Resolve Export

The analyzer generates `FCPXML` format timelines for DaVinci Resolve.

The desktop app provides a native save dialog so you can choose the export destination. The backend writes to `generated/timeline.fcpxml` by default.

## Development & Testing

**Run Python tests:**

```bash
npm run test:python
```

**Build desktop app:**

```bash
npm run build:desktop
```

**Run analyzer directly (for debugging):**

```bash
npm run process
npm run export
```

## Documentation

- 📖 [docs/manifesto.md](docs/manifesto.md) — Project vision and principles
- 📖 [docs/analyzer-pipeline.md](docs/analyzer-pipeline.md) — Detailed walkthrough of the analysis pipeline
- 🔍 [docs/research.md](docs/research.md) — Research notes and design decisions
- ⚙️ [.env.example](.env.example) — All environment variable defaults

## Architecture Specs

The project uses OpenSpec for architectural documentation:

- `openspec/specs/clip-deduplication-semantic/` — CLIP embedding-based near-duplicate detection
- `openspec/specs/segment-deduplication/` — Segment deduplication with histogram fallback
- `openspec/specs/audio-signal-layer/` — Audio signal extraction and analysis
- `openspec/specs/vision-prefilter-pipeline/` — Visual signal preprocessing
- `openspec/specs/processing-workflow/` — Pipeline orchestration and phase ordering
