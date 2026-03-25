# Setup & Requirements

## System Requirements

### Always Required

- **Node.js** 18+
- **npm** 9+
- **Python** 3.12+
- **Xcode Command Line Tools** (macOS: `xcode-select --install`)
- **Rust / Cargo** (for Tauri desktop shell; installer will prompt on first build)

### For Media Analysis

These are installed automatically by `npm run setup`:

- **ffmpeg** — Frame and audio extraction
- **ffprobe** — Optional; metadata probing (ffmpeg includes this)
- **PySceneDetect** — Optional; improved scene boundary detection
- **faster-whisper** — Optional; speech transcription

### For MLX-VLM Local (Optional)

If you choose the MLX provider during setup, these are installed automatically:

- **mlx** — Apple Silicon ML framework
- **mlx-vlm** — Vision-language model runtime
- **torch**, **torchvision**, **pillow** — Model dependencies

Only required if using `TIMELINE_AI_PROVIDER=mlx-vlm-local`.

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/roughcut-stdio
cd roughcut-stdio
```

### 2. Run Setup

The setup script automates most of the heavy lifting:

```bash
npm run setup
```

This will:
- Install Node.js dependencies (`npm install`)
- Create a Python virtual environment
- Install Python dependencies
- Install ffmpeg via Homebrew (if not already present)
- Check for Xcode Command Line Tools
- Download and prepare the MLX runtime and model cache (if chosen)

**During setup, you'll be prompted:**
- Do you want to install MLX-VLM? (yes/no)
- If yes, which model size? (small/medium/large)

Choose based on your system:
- **Small** (Qwen3.5-0.8B) — Recommended for most Macs; fast and accurate enough
- **Medium** (Qwen3.5-3B) — Better quality; slower on M1/M2
- **Large** (Qwen3.5-9B) — Best quality; requires LM Studio server

### 3. Verify Installation

```bash
npm run check:ai
```

This checks that all required dependencies are available and working.

### 4. Open the Desktop App

```bash
npm run view
```

This launches the desktop app in development mode.

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
python3 -m venv venv
source venv/bin/activate
pip install -r services/analyzer/requirements.txt
```

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
4. Review the shortlisted segments in the timeline
5. Click "Export" to save a DaVinci Resolve timeline

For detailed configuration options, see [docs/configuration.md](configuration.md).
