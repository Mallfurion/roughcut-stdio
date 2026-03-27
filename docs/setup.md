# Setup & Requirements

## System Requirements

### Always Required

- **Node.js** 18+
- **npm** 9+
- **Python** 3.12+
- **Xcode Command Line Tools** (macOS: `xcode-select --install`)
- **Rust / Cargo** (for the Tauri desktop shell; `npm run setup` installs it via Homebrew on macOS when possible)

### For Media Analysis

These are installed automatically by `npm run setup`:

- **ffmpeg** — Frame and audio extraction
- **ffprobe** — Optional; metadata probing (ffmpeg includes this)
- **PySceneDetect** — Optional; improved scene boundary detection
- **faster-whisper** — Installed by setup when `TIMELINE_TRANSCRIPT_PROVIDER!=disabled`; used for local speech transcription

### For MLX-VLM Local (Optional)

If `TIMELINE_AI_PROVIDER=mlx-vlm-local` during setup, these are installed automatically:

- **mlx** — Apple Silicon ML framework
- **mlx-vlm** — Vision-language model runtime
- **torch**, **torchvision**, **pillow** — Model dependencies

Only required if using `TIMELINE_AI_PROVIDER=mlx-vlm-local`.

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/Mallfurion/roughcut-stdio.git
cd roughcut-stdio
```

### 2. Run Setup

The setup script is driven by your current `.env` and `.env.local` settings. `.env.local` overrides `.env`.

If you want to change the runtime before installing dependencies, copy the example file first:

```bash
cp .env.example .env.local
```

Then edit values like `TIMELINE_AI_PROVIDER`, `TIMELINE_TRANSCRIPT_PROVIDER`, or `TIMELINE_SKIP_MODEL_DOWNLOAD` before running setup.

Now run:

```bash
npm run setup
```

This will:
- Install Node.js dependencies (`npm install`)
- Create a Python virtual environment
- Install the analyzer package into `.venv`
- Install ffmpeg via Homebrew (if not already present)
- Check for Xcode Command Line Tools
- Check for Rust/Cargo and install it with Homebrew on macOS if missing
- Prepare `generated/`
- Create a default `media -> fixtures/sample-media` symlink when no media path is configured

The installed Python extras are derived from the current environment:

- `clip` is installed by default
- `transcript` is installed unless `TIMELINE_TRANSCRIPT_PROVIDER=disabled`
- `mlx_vlm` is installed only when `TIMELINE_AI_PROVIDER=mlx-vlm-local`

Model bootstrapping is also env-driven:

- CLIP weights are bootstrapped by default
- MLX-VLM weights are bootstrapped only for `TIMELINE_AI_PROVIDER=mlx-vlm-local`
- `TIMELINE_SKIP_MODEL_DOWNLOAD=1` skips model downloads entirely

### 3. Verify Installation

```bash
npm run check:ai
```

This checks that the configured runtime is available and working.

The output now includes:

- the configured and effective AI provider
- transcript runtime status and model size
- runtime reliability mode across AI, transcript, semantic validation, and cache
- degraded-mode and intentional-skip reasons when optional layers are unavailable or bounded

If you want transcript-backed speech analysis, verify that `faster-whisper` is available. The analyzer can still run without it, but transcript runtime will report `unavailable` and speech clips will use deterministic fallback instead of transcript excerpts.

When transcript support is active, the analyzer does not fully transcribe every clip with audio. It reuses transcript cache on reruns, skips clearly weak candidates, and can run a short transcript probe on borderline assets before deciding whether a full transcription pass is worth the cost.

By default, `npm run setup` installs transcript support because `TIMELINE_TRANSCRIPT_PROVIDER` defaults to `auto`. If you want a lighter install without local transcription, set `TIMELINE_TRANSCRIPT_PROVIDER=disabled` before running setup.

If you want MLX-VLM support, set `TIMELINE_AI_PROVIDER=mlx-vlm-local` before running setup so the matching extra and model bootstrap path are included.

### 4. Open the Desktop App

```bash
npm run view
```

This launches the Tauri desktop app in development mode.

---

## Troubleshooting Setup

### ffmpeg not found after setup

Homebrew install may have failed. Install manually:

```bash
brew install ffmpeg
```

Or download from [ffmpeg.org](https://ffmpeg.org/download.html).

### Python virtual environment not created

Create manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e './services/analyzer[clip,transcript]'
```

If you use `TIMELINE_AI_PROVIDER=mlx-vlm-local`, include the `mlx_vlm` extra as well.

### MLX installation fails on Intel Mac

MLX is Apple Silicon only. The setup script detects this and skips MLX installation. Use `TIMELINE_AI_PROVIDER=lmstudio` instead with a local LM Studio server.

### Rust not installed

Rust is needed only for building the Tauri desktop app. If you see a Rust error:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
npm run build:desktop
```

Or install via Homebrew:

```bash
brew install rust
```

### Port already in use (LM Studio)

If you're running an LM Studio server and see a port conflict:

```bash
TIMELINE_AI_BASE_URL=http://127.0.0.1:8000/v1 npm run process
```

Replace `8000` with the port LM Studio is actually using.

---

## Quick Start After Installation

Once setup completes:

1. Open the desktop app: `npm run view`
2. Click "Choose Media Folder" and select a directory with video files
3. Click "Process" and wait for analysis to complete
4. Review the recommended segments, provenance, and generated timeline preview
5. Optionally override or clear best takes per clip
6. Click "Export" to save a DaVinci Resolve timeline built from the current desktop review state

For detailed configuration options, see [docs/configuration.md](configuration.md).
