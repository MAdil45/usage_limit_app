# AI Usage Widget

A local Linux desktop widget for keeping ChatGPT/Codex and Claude plan limits in view. The app provides one focused interface: a compact, frosted-glass usage gadget.

It displays the ChatGPT/Codex weekly limit and Claude's current 5-hour session plus weekly limit. The widget can be moved by dragging its empty header, resized from any edge or corner, and brought forward by launching it again. Usage data stays on the local computer in `~/.config/ai-usage-widget/usage.json`.

## Requirements

On Ubuntu/Debian, install GTK and WebKit:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

Chrome is required for automatic usage updates, with active signed-in ChatGPT/Codex and Claude sessions.

## Run

```bash
git clone https://github.com/MAdil45/usage_limit_app.git
cd usage_limit_app
./run-widget.sh
```

## Install as a Linux desktop app

```bash
./install-linux-app.sh
```

Find **AI Usage Widget** in the Linux app launcher. To remove the launcher later without deleting the project or saved usage data:

```bash
./uninstall-linux-app.sh
```

## Enable automatic usage updates

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this repository's `browser-companion` directory.
4. Keep the extension enabled, and reload it after updating the repository.

At launch, both providers refresh once. After a 30-second quiet period, Claude refreshes every 30 seconds and ChatGPT/Codex every minute through their signed-in usage pages. Refreshes stop when the widget closes.

## Project layout

- `webview_widget.py` — the Glass widget interface and local update server.
- `run-widget.sh` — the single-instance application launcher.
- `browser-companion/` — the Chrome extension that reads usage values from signed-in provider pages.
- `codex_usage_sync.py` — the local ChatGPT/Codex usage synchronization helper.
- `install-linux-app.sh` — installs the desktop launcher and icon for the current user.

## Privacy

The companion sends only the provider name, usage percentage, and displayed reset label to the local listener at `http://127.0.0.1:8765`. It does not save or send passwords, cookies, API keys, prompts, chats, or account identifiers.
