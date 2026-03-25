#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

GENERATED_DIR="${ROOT_DIR}/generated"

echo "Cleaning generated folder: $GENERATED_DIR"

if [ -d "$GENERATED_DIR" ]; then
  rm -rf "$GENERATED_DIR"
  echo "Generated folder deleted successfully"
else
  echo "Generated folder does not exist"
fi
