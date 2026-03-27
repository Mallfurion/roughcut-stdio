#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)"
TAURI_DIR="$REPO_ROOT/apps/desktop/src-tauri"
STAGE_ROOT="$TAURI_DIR/.runtime-bundle"
RUNTIME_ROOT="$STAGE_ROOT/runtime"
PYTHON_BIN="$RUNTIME_ROOT/python/bin/python3"
RUNTIME_BIN_DIR="$RUNTIME_ROOT/bin"
CHECK_SCRIPT="$STAGE_ROOT/services/analyzer/scripts/check_ai_provider.py"
SCAN_SCRIPT="$STAGE_ROOT/services/analyzer/scripts/scan_media_root.py"
WRITE_ARTIFACTS_SCRIPT="$STAGE_ROOT/services/analyzer/scripts/write_process_artifacts.py"
EXPORT_SCRIPT="$STAGE_ROOT/services/analyzer/scripts/export_fcpxml.py"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/roughcut-desktop-verify.XXXXXX")"
MEDIA_DIR="$WORK_DIR/media"
ANALYSIS_DIR="$WORK_DIR/analysis"
BENCHMARK_DIR="$WORK_DIR/benchmarks"
PROCESS_OUTPUT="$WORK_DIR/process-output.txt"
PROCESS_SUMMARY="$WORK_DIR/process-summary.txt"
PROCESS_LOG="$WORK_DIR/process.log"
RUN_OUTPUT="$WORK_DIR/run-output.log"
PROJECT_JSON="$WORK_DIR/project.json"
EXPORT_XML="$WORK_DIR/timeline.fcpxml"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$MEDIA_DIR" "$ANALYSIS_DIR" "$BENCHMARK_DIR"

echo "Staging packaged runtime resources..."
ROUGHCUT_DESKTOP_STAGE_RUNTIME=1 cargo check --release --manifest-path "$TAURI_DIR/Cargo.toml" >/dev/null

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing packaged python wrapper: $PYTHON_BIN" >&2
  exit 1
fi

chmod +x "$RUNTIME_BIN_DIR/ffmpeg" "$RUNTIME_BIN_DIR/ffprobe"

if [ ! -x "$RUNTIME_BIN_DIR/ffmpeg" ] || [ ! -x "$RUNTIME_BIN_DIR/ffprobe" ]; then
  echo "Missing bundled ffmpeg/ffprobe under $RUNTIME_BIN_DIR" >&2
  exit 1
fi

export PATH="$RUNTIME_BIN_DIR:$PATH"
export HF_HOME="$WORK_DIR/hf"
export HF_HUB_CACHE="$HF_HOME/hub"
export TORCH_HOME="$WORK_DIR/torch"
export XDG_CACHE_HOME="$WORK_DIR/cache"
export TIMELINE_AI_PROVIDER="deterministic"
export TIMELINE_TRANSCRIPT_PROVIDER="disabled"
export TIMELINE_TRANSCRIPT_MODEL_SIZE="small"
export TIMELINE_AI_CLIP_ENABLED="false"
export TIMELINE_PROJECT_NAME="Packaged Runtime Verification"
export TIMELINE_STORY_PROMPT="Build a coherent rough cut from the strongest visual beats."

echo "Generating deterministic smoke-test media with bundled ffmpeg..."
"$RUNTIME_BIN_DIR/ffmpeg" \
  -hide_banner \
  -loglevel error \
  -f lavfi \
  -i "testsrc=size=640x360:rate=24:duration=2" \
  -f lavfi \
  -i "anullsrc=r=48000:cl=stereo" \
  -shortest \
  -c:v libx264 \
  -pix_fmt yuv420p \
  -c:a aac \
  "$MEDIA_DIR/smoke.mp4"

echo "Checking deterministic packaged runtime readiness..."
CHECK_OUTPUT="$("$PYTHON_BIN" "$CHECK_SCRIPT")"
printf '%s\n' "$CHECK_OUTPUT"
printf '%s\n' "$CHECK_OUTPUT" | grep -q "runtime_ready: yes"
printf '%s\n' "$CHECK_OUTPUT" | grep -q "transcript_provider_configured: disabled"

echo "Running transcript-disabled deterministic process smoke test..."
STARTED_AT="$(date -u "+%Y-%m-%dT%H:%M:%SZ")"
if ! "$PYTHON_BIN" "$SCAN_SCRIPT" \
  "$TIMELINE_PROJECT_NAME" \
  "$MEDIA_DIR" \
  "$TIMELINE_STORY_PROMPT" \
  --artifacts-root "$ANALYSIS_DIR" \
  >"$PROJECT_JSON" 2>"$RUN_OUTPUT"; then
  cat "$RUN_OUTPUT" >&2
  exit 1
fi
COMPLETED_AT="$(date -u "+%Y-%m-%dT%H:%M:%SZ")"

"$PYTHON_BIN" "$WRITE_ARTIFACTS_SCRIPT" \
  --project-json "$PROJECT_JSON" \
  --process-log "$PROCESS_LOG" \
  --process-summary "$PROCESS_SUMMARY" \
  --benchmark-root "$BENCHMARK_DIR" \
  --process-output "$PROCESS_OUTPUT" \
  --run-process-output "$RUN_OUTPUT" \
  --run-id "packaged-runtime-verify" \
  --started-at "$STARTED_AT" \
  --completed-at "$COMPLETED_AT" \
  --total-runtime-sec "1" \
  --media-dir "$MEDIA_DIR" \
  --media-dir-input "$MEDIA_DIR"

[ -s "$PROJECT_JSON" ]
[ -s "$PROCESS_LOG" ]
[ -s "$PROCESS_SUMMARY" ]
[ -s "$BENCHMARK_DIR/history.jsonl" ]

echo "Smoke-testing Resolve export..."
"$PYTHON_BIN" "$EXPORT_SCRIPT" "$PROJECT_JSON" >"$EXPORT_XML"
grep -q "<fcpxml" "$EXPORT_XML"

echo "Verifying staged media tools are not linked to Homebrew dylibs..."
if otool -L "$RUNTIME_BIN_DIR/ffmpeg" | grep -q "/opt/homebrew/"; then
  echo "Bundled ffmpeg still links against /opt/homebrew" >&2
  exit 1
fi
if otool -L "$RUNTIME_BIN_DIR/ffprobe" | grep -q "/opt/homebrew/"; then
  echo "Bundled ffprobe still links against /opt/homebrew" >&2
  exit 1
fi

echo "Packaged runtime verification passed."
