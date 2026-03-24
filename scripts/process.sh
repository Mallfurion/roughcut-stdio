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
TMP_OUTPUT_JSON="${ROOT_DIR}/generated/project.json.tmp"
LOG_FILE="${ROOT_DIR}/generated/process.log"
SUMMARY_FILE="${ROOT_DIR}/generated/process-summary.txt"
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
  > "$TMP_OUTPUT_JSON"

mv "$TMP_OUTPUT_JSON" "$OUTPUT_JSON"

{
  echo "processed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "project_json=$OUTPUT_JSON"
  echo "media_dir=$MEDIA_DIR"
} > "$LOG_FILE"

"$PYTHON_BIN" - <<'PY' > "$SUMMARY_FILE"
import json
from pathlib import Path

payload = json.loads(Path("generated/project.json").read_text())
assets = payload["assets"]
source_only = [asset for asset in assets if asset.get("has_proxy") is False]
proxy_backed = [asset for asset in assets if asset.get("has_proxy") is not False]

print(f"Assets: {len(assets)}")
print(f"Proxy-backed assets: {len(proxy_backed)}")
print(f"Source-only assets: {len(source_only)}")

if source_only:
    print("")
    print("Source-only clips:")
    for asset in source_only[:50]:
        print(f"- {asset['interchange_reel_name']} -> {asset['source_path']}")
        reason = asset.get("proxy_match_reason")
        if reason:
            print(f"  reason: {reason}")
PY

echo "Generated timeline project at $OUTPUT_JSON"
echo "Process summary written to $SUMMARY_FILE"
echo "Next:"
echo "  npm run view"
echo "  npm run export"
