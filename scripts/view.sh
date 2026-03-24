#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Starting timeline selector app..."
echo "If you have not processed media yet, run: npm run process"
npm run dev:web
