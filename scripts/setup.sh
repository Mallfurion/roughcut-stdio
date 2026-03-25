#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load optional local environment configuration.
# `.env.local` overrides `.env`.
. "${ROOT_DIR}/scripts/lib/load_env.sh"

select_python() {
  if [ -n "${TIMELINE_PYTHON:-}" ] && [ -x "${TIMELINE_PYTHON}" ]; then
    echo "${TIMELINE_PYTHON}"
    return 0
  fi

  for candidate in /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 python3; do
    if ! command -v "$candidate" >/dev/null 2>&1 && [ ! -x "$candidate" ]; then
      continue
    fi

    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
    then
      if [ -x "$candidate" ]; then
        echo "$candidate"
      else
        command -v "$candidate"
      fi
      return 0
    fi
  done

  echo "No Python 3.12+ interpreter found." >&2
  exit 1
}

PYTHON_BIN="$(select_python)"

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is already available."
    return 0
  fi

  local os_name
  os_name="$(uname -s)"
  if [ "$os_name" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    echo "ffmpeg is missing. Installing it with Homebrew..."
    brew install ffmpeg
    return 0
  fi

  echo "ffmpeg is not installed."
  echo "Automatic installation is only supported during setup on macOS with Homebrew."
  echo "Install ffmpeg manually, then rerun npm run setup."
  return 1
}

ensure_rust() {
  if command -v cargo >/dev/null 2>&1 && command -v rustc >/dev/null 2>&1; then
    echo "Rust toolchain is already available."
    return 0
  fi

  local os_name
  os_name="$(uname -s)"
  if [ "$os_name" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    echo "Rust toolchain is missing. Installing it with Homebrew..."
    brew install rust
    return 0
  fi

  echo "Rust toolchain is not installed."
  echo "Automatic installation is only supported during setup on macOS with Homebrew."
  echo "Install Rust manually, then rerun npm run setup."
  return 1
}

ensure_macos_build_tools() {
  local os_name
  os_name="$(uname -s)"
  if [ "$os_name" != "Darwin" ]; then
    return 0
  fi

  if xcode-select -p >/dev/null 2>&1; then
    echo "Xcode Command Line Tools are available."
    return 0
  fi

  echo "Xcode Command Line Tools are required to build the desktop app."
  echo "Run: xcode-select --install"
  echo "Then rerun npm run setup."
  return 1
}

echo "Installing JavaScript dependencies..."
npm install

echo "Using Python interpreter: $PYTHON_BIN"
echo "Creating Python virtual environment..."
"$PYTHON_BIN" -m venv --clear .venv

export PIP_DISABLE_PIP_VERSION_CHECK=1

echo "Preparing generated output folder..."
mkdir -p "$ROOT_DIR/generated"

ensure_ffmpeg
ensure_macos_build_tools
ensure_rust

echo "Installing analyzer package into the virtual environment..."
install_extras=""

# CLIP is enabled by default
install_extras="${install_extras}clip,"

if [ "${TIMELINE_AI_PROVIDER:-deterministic}" = "mlx-vlm-local" ]; then
  install_extras="${install_extras}mlx_vlm,"
fi

if [ -n "${install_extras}" ]; then
  # Remove trailing comma
  install_extras="${install_extras%,}"
  echo "Installing analyzer with extras: $install_extras"
  "$ROOT_DIR/.venv/bin/python3" -m pip install -e "./services/analyzer[${install_extras}]"
else
  "$ROOT_DIR/.venv/bin/python3" -m pip install -e "./services/analyzer"
fi

if [ "${TIMELINE_SKIP_MODEL_DOWNLOAD:-0}" != "1" ]; then
  echo ""
  echo "Bootstrapping AI models..."

  if [ "${TIMELINE_AI_PROVIDER:-deterministic}" = "mlx-vlm-local" ]; then
    echo "Bootstrapping MLX-VLM local model..."
    "$ROOT_DIR/.venv/bin/python3" services/analyzer/scripts/bootstrap_mlx_vlm.py
  fi

  # CLIP is enabled by default, download its model
  echo "Bootstrapping CLIP semantic scoring model..."
  "$ROOT_DIR/.venv/bin/python3" services/analyzer/scripts/bootstrap_clip.py
else
  echo "Skipping model download because TIMELINE_SKIP_MODEL_DOWNLOAD=1"
fi

if [ -n "${TIMELINE_MEDIA_DIR:-}" ]; then
  echo "Configured external media root via TIMELINE_MEDIA_DIR=$TIMELINE_MEDIA_DIR"
elif [ ! -e "$ROOT_DIR/media" ]; then
  echo "Creating default media symlink -> fixtures/sample-media"
  ln -s "$ROOT_DIR/fixtures/sample-media" "$ROOT_DIR/media"
else
  echo "Keeping existing media path at $ROOT_DIR/media"
fi

echo
echo "Setup complete."
echo "Main flow:"
echo "  npm run view"
echo
echo "Inside the desktop app:"
echo "  1. choose runtime"
echo "  2. choose media folder"
echo "  3. process footage"
echo "  4. review shots"
echo "  5. export timeline"
echo "  npm run check:ai"
echo
echo "Media root selection:"
echo "  TIMELINE_MEDIA_DIR=/absolute/path/to/footage npm run process"
echo "  cp .env.example .env.local"
echo
echo "Optional API setup:"
echo "  source .venv/bin/activate"
echo "  python3 -m pip install -e './services/analyzer[api]'"
