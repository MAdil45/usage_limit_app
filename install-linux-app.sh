#!/usr/bin/env bash
# Installs a per-user desktop launcher. It does not require sudo.
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_THEME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
ICON_DIR="$ICON_THEME_DIR/scalable/apps"
LAUNCHER="$APPLICATIONS_DIR/ai-usage-widget.desktop"

mkdir -p "$APPLICATIONS_DIR" "$ICON_DIR"
sed "s|@APP_DIR@|$APP_DIR|g" "$APP_DIR/ai-usage-widget.desktop.in" > "$LAUNCHER"
install -m 644 "$APP_DIR/assets/ai-usage-widget.svg" "$ICON_DIR/ai-usage-widget.svg"
chmod 755 "$APP_DIR/run-glass-web.sh" "$LAUNCHER"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$ICON_THEME_DIR" >/dev/null 2>&1 || true
fi

echo "Installed AI Usage Widget. Find it in your app launcher, or run: gtk-launch ai-usage-widget"
