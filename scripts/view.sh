#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "${ROOT_DIR}/scripts/lib/load_env.sh"

echo "Starting Roughcut Stdio desktop app..."
echo "If you have not processed media yet, the desktop app will still open and you can run setup/process there."
npm run dev:desktop
