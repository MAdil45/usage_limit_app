#!/usr/bin/env bash
# Removes only the per-user desktop launcher; project files remain untouched.
set -euo pipefail

APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_THEME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
rm -f "$APPLICATIONS_DIR/ai-usage-widget.desktop"
rm -f "$ICON_THEME_DIR/scalable/apps/ai-usage-widget.svg"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$ICON_THEME_DIR" >/dev/null 2>&1 || true
fi
echo "Removed the AI Usage Widget launcher and icon."
