#!/usr/bin/env bash
# Removes only the per-user desktop launcher; project files remain untouched.
set -euo pipefail

APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
rm -f "$APPLICATIONS_DIR/ai-usage-widget.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
echo "Removed the AI Usage Widget launcher."
