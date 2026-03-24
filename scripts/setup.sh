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

echo "Installing JavaScript dependencies..."
npm install

echo "Using Python interpreter: $PYTHON_BIN"
echo "Creating Python virtual environment..."
"$PYTHON_BIN" -m venv --clear .venv

export PIP_DISABLE_PIP_VERSION_CHECK=1

echo "Preparing generated output folder..."
mkdir -p "$ROOT_DIR/generated"

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
echo "  npm run process"
echo "  npm run view"
echo "  npm run export"
echo
echo "Media root selection:"
echo "  TIMELINE_MEDIA_DIR=/absolute/path/to/footage npm run process"
echo "  cp .env.example .env.local"
echo
echo "Optional API setup:"
echo "  source .venv/bin/activate"
echo "  python3 -m pip install -e './services/analyzer[api]'"
