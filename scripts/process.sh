#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

MEDIA_DIR="${ROOT_DIR}/media"
OUTPUT_JSON="${ROOT_DIR}/generated/project.json"
LOG_FILE="${ROOT_DIR}/generated/process.log"
PROJECT_NAME="${TIMELINE_PROJECT_NAME:-Timeline Cutter Project}"
STORY_PROMPT="${TIMELINE_STORY_PROMPT:-Build a coherent rough cut from the strongest visual and spoken beats.}"

if [ ! -e "$MEDIA_DIR" ]; then
  echo "Missing media path at $MEDIA_DIR"
  echo "Run 'npm run setup' first, or create a symlink named 'media' that points to your footage folder."
  exit 1
fi

mkdir -p "${ROOT_DIR}/generated"

echo "Processing media from ${MEDIA_DIR}"
"$PYTHON_BIN" services/analyzer/scripts/scan_media_root.py \
  "$PROJECT_NAME" \
  "$MEDIA_DIR" \
  "$STORY_PROMPT" \
  > "$OUTPUT_JSON"

{
  echo "processed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "project_json=$OUTPUT_JSON"
  echo "media_dir=$MEDIA_DIR"
} > "$LOG_FILE"

echo "Generated timeline project at $OUTPUT_JSON"
echo "Next:"
echo "  npm run view"
echo "  npm run export"
