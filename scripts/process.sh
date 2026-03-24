#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load optional local environment configuration.
# `.env.local` overrides `.env`.
. "${ROOT_DIR}/scripts/lib/load_env.sh"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

MEDIA_DIR_INPUT="${TIMELINE_MEDIA_DIR:-${ROOT_DIR}/media}"
if [[ "$MEDIA_DIR_INPUT" = /* ]]; then
  MEDIA_DIR="$MEDIA_DIR_INPUT"
else
  MEDIA_DIR="${ROOT_DIR}/${MEDIA_DIR_INPUT#./}"
fi
OUTPUT_JSON="${ROOT_DIR}/generated/project.json"
TMP_OUTPUT_JSON="${ROOT_DIR}/generated/project.json.tmp"
LOG_FILE="${ROOT_DIR}/generated/process.log"
SUMMARY_FILE="${ROOT_DIR}/generated/process-summary.txt"
PROJECT_NAME="${TIMELINE_PROJECT_NAME:-Timeline Cutter Project}"
STORY_PROMPT="${TIMELINE_STORY_PROMPT:-Build a coherent rough cut from the strongest visual and spoken beats.}"

if [ ! -e "$MEDIA_DIR" ]; then
  echo "Missing media path at $MEDIA_DIR"
  echo "Set TIMELINE_MEDIA_DIR to your footage path, or create the default repo media folder."
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

AI_STATUS_LINES="$("$PYTHON_BIN" - <<'PY'
from services.analyzer.app.ai import inspect_ai_provider_status, load_ai_analysis_config

status = inspect_ai_provider_status()
analysis = load_ai_analysis_config()
print(f"ai_provider_configured={status.configured_provider}")
print(f"ai_provider_effective={status.effective_provider}")
print(f"ai_model={status.model}")
print(f"ai_base_url={status.base_url}")
print(f"ai_available={str(status.available).lower()}")
print(f"ai_detail={status.detail}")
print(f"ai_mode={analysis.mode}")
print(f"ai_max_segments_per_asset={analysis.max_segments_per_asset}")
print(f"ai_max_keyframes={analysis.max_keyframes_per_segment}")
print(f"ai_keyframe_max_width={analysis.keyframe_max_width}")
print(f"ai_concurrency={analysis.concurrency}")
print(f"ai_cache_enabled={str(analysis.cache_enabled).lower()}")
PY
)"

{
  echo "processed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "project_json=$OUTPUT_JSON"
  echo "media_dir=$MEDIA_DIR"
  echo "media_dir_input=$MEDIA_DIR_INPUT"
  printf '%s\n' "$AI_STATUS_LINES"
} > "$LOG_FILE"

"$PYTHON_BIN" - <<'PY' > "$SUMMARY_FILE"
import json
from pathlib import Path

payload = json.loads(Path("generated/project.json").read_text())
assets = payload["assets"]
source_only = [asset for asset in assets if asset.get("has_proxy") is False]
proxy_backed = [asset for asset in assets if asset.get("has_proxy") is not False]
analysis_summary = payload.get("project", {}).get("analysis_summary", {})

print(f"Assets: {len(assets)}")
print(f"Proxy-backed assets: {len(proxy_backed)}")
print(f"Source-only assets: {len(source_only)}")
if analysis_summary:
    print("")
    print(f"Prefilter sampled frames: {analysis_summary.get('prefilter_sample_count', 0)}")
    print(f"Candidate segments: {analysis_summary.get('candidate_segment_count', 0)}")
    print(f"Prefilter shortlisted: {analysis_summary.get('prefilter_shortlisted_count', 0)}")
    print(f"VLM target segments: {analysis_summary.get('vlm_target_count', 0)}")
    print(f"Filtered before VLM: {analysis_summary.get('filtered_before_vlm_count', 0)}")

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
