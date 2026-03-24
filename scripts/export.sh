#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

INPUT_JSON="${ROOT_DIR}/generated/project.json"
OUTPUT_XML="${ROOT_DIR}/generated/timeline.fcpxml"

if [ ! -f "$INPUT_JSON" ]; then
  echo "Missing generated project at $INPUT_JSON"
  echo "Run 'npm run process' first."
  exit 1
fi

"$PYTHON_BIN" services/analyzer/scripts/export_fcpxml.py "$INPUT_JSON" > "$OUTPUT_XML"

echo "Exported Resolve timeline to $OUTPUT_XML"
