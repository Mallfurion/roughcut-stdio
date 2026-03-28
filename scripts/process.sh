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
PROCESS_OUTPUT_FILE="${ROOT_DIR}/generated/process-output.txt"
BENCHMARK_ROOT="${ROOT_DIR}/generated/benchmarks"
VLM_DEBUG_FILE="${ROOT_DIR}/generated/analysis/vlm-debug.jsonl"
PROJECT_NAME="${TIMELINE_PROJECT_NAME:-Roughcut Stdio Project}"
STORY_PROMPT="${TIMELINE_STORY_PROMPT:-Build a coherent rough cut from the strongest visual and spoken beats.}"

if [ ! -e "$MEDIA_DIR" ]; then
  if [ -t 2 ]; then
    printf '\033[31mERROR: Missing media path at %s\033[0m\n' "$MEDIA_DIR" >&2
  else
    printf 'ERROR: Missing media path at %s\n' "$MEDIA_DIR" >&2
  fi
  echo "Set TIMELINE_MEDIA_DIR to your footage path, or create the default repo media folder." >&2
  exit 1
fi

mkdir -p "${ROOT_DIR}/generated"
: > "$PROCESS_OUTPUT_FILE"
rm -f "$VLM_DEBUG_FILE"

emit_output() {
  printf '%s\n' "$1" | tee -a "$PROCESS_OUTPUT_FILE"
}

emit_summary_line() {
  local line="$1"
  printf '%s\n' "$line" >> "$PROCESS_OUTPUT_FILE"

  if [ -t 1 ]; then
    case "$line" in
      Workload:*)
        printf '\033[32m%s\033[0m\n' "$line"
        ;;
      Total\ runtime:*)
        printf '\033[32m%s\033[0m\n' "$line"
        ;;
      $'\t'*)
        printf '\033[32m%s\033[0m\n' "$line"
        ;;
      *)
        printf '%s\n' "$line"
        ;;
    esac
  else
    printf '%s\n' "$line"
  fi
}

emit_file() {
  local path="$1"
  while IFS= read -r line || [ -n "$line" ]; do
    emit_output "$line"
  done < "$path"
}

emit_summary_file() {
  local path="$1"
  while IFS= read -r line || [ -n "$line" ]; do
    emit_summary_line "$line"
  done < "$path"
}

RUN_ID="$("$PYTHON_BIN" - <<'PY'
from datetime import datetime, timezone
from uuid import uuid4

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"{stamp}-{uuid4().hex[:6]}")
PY
)"
RUN_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_START_EPOCH="$("$PYTHON_BIN" - <<'PY'
import time

print(f"{time.time():.6f}")
PY
)"
RUN_BENCHMARK_DIR="${BENCHMARK_ROOT}/${RUN_ID}"
RUN_BENCHMARK_FILE="${RUN_BENCHMARK_DIR}/benchmark.json"
RUN_PROCESS_OUTPUT_FILE="${RUN_BENCHMARK_DIR}/process-output.txt"
BENCHMARK_HISTORY_FILE="${BENCHMARK_ROOT}/history.jsonl"

"$PYTHON_BIN" services/analyzer/scripts/scan_media_root.py \
  "$PROJECT_NAME" \
  "$MEDIA_DIR" \
  "$STORY_PROMPT" \
  --process-output-file "$PROCESS_OUTPUT_FILE" \
  > "$TMP_OUTPUT_JSON"

mv "$TMP_OUTPUT_JSON" "$OUTPUT_JSON"
RUN_COMPLETED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_END_EPOCH="$("$PYTHON_BIN" - <<'PY'
import time

print(f"{time.time():.6f}")
PY
)"
TOTAL_RUNTIME_SEC="$("$PYTHON_BIN" - "$RUN_START_EPOCH" "$RUN_END_EPOCH" <<'PY'
import sys

print(f"{float(sys.argv[2]) - float(sys.argv[1]):.3f}")
PY
)"

"$PYTHON_BIN" services/analyzer/scripts/write_process_artifacts.py \
  --project-json "$OUTPUT_JSON" \
  --process-log "$LOG_FILE" \
  --process-summary "$SUMMARY_FILE" \
  --benchmark-root "$BENCHMARK_ROOT" \
  --process-output "$PROCESS_OUTPUT_FILE" \
  --run-process-output "$RUN_PROCESS_OUTPUT_FILE" \
  --run-id "$RUN_ID" \
  --started-at "$RUN_STARTED_AT" \
  --completed-at "$RUN_COMPLETED_AT" \
  --total-runtime-sec "$TOTAL_RUNTIME_SEC" \
  --media-dir "$MEDIA_DIR" \
  --media-dir-input "$MEDIA_DIR_INPUT" \
  --vlm-debug-file "$VLM_DEBUG_FILE"

emit_summary_file "$SUMMARY_FILE"
emit_output "Next:"
emit_output "  npm run view"
emit_output "  npm run export"

mkdir -p "$RUN_BENCHMARK_DIR"
cp "$PROCESS_OUTPUT_FILE" "$RUN_PROCESS_OUTPUT_FILE"
