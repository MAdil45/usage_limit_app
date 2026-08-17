#!/usr/bin/env bash
# Installs a per-user desktop launcher. It does not require sudo.
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
LAUNCHER="$APPLICATIONS_DIR/ai-usage-widget.desktop"

mkdir -p "$APPLICATIONS_DIR"
sed "s|@APP_DIR@|$APP_DIR|g" "$APP_DIR/ai-usage-widget.desktop.in" > "$LAUNCHER"
chmod 755 "$APP_DIR/run-glass-web.sh" "$LAUNCHER"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "Installed AI Usage Widget. Find it in your app launcher, or run: gtk-launch ai-usage-widget"
