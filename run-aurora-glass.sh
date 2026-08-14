#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/run-codex-sync.sh" &
SYNC_PID=$!
trap 'kill "$SYNC_PID" 2>/dev/null || true' EXIT INT TERM
/usr/bin/python3 "$SCRIPT_DIR/modern_widget.py" --theme aurora
