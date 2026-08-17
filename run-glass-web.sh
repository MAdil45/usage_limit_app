#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# The widget is single-instance.  A second click in the app launcher brings
# the existing widget forward instead of starting another process that cannot
# bind its local companion-extension port.
if command -v curl >/dev/null 2>&1 && curl --fail --silent --max-time 1 --output /dev/null http://127.0.0.1:8765/show 2>/dev/null; then
  exit 0
fi
exec /usr/bin/python3 "$SCRIPT_DIR/webview_widget.py" --theme glass
