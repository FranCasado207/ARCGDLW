#!/usr/bin/env bash
# Starts the backend and the Tauri dev app together for local development.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

export ARCGDLW_DEV_TOKEN="${ARCGDLW_DEV_TOKEN:-devtoken}"
export PYTHONPATH=src

uv run python -m arcgdlw.main --serve --port 8734 &
BACKEND_PID=$!

cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

npx --prefix frontend tauri dev
