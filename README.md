# AI Usage Widget

A local Linux desktop widget for keeping ChatGPT/Codex and Claude plan limits in view. The app provides one focused interface: a compact, frosted-glass usage gadget.

It displays the current 5-hour session and weekly limit for both ChatGPT/Codex and Claude. The widget can be moved by dragging its empty header, resized from any edge or corner, and brought forward by launching it again. Usage data stays on the local computer in `~/.config/ai-usage-widget/usage.json`.

## Requirements

On Ubuntu/Debian, install GTK and WebKit:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

You also need:

- The ChatGPT/Codex desktop app installed and signed in. The widget reads ChatGPT plan limits through the app's local authenticated service.
- Chrome signed in to Claude, plus the included browser companion extension described below.

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

## Enable Claude updates

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this repository's `browser-companion` directory.
4. Keep the extension enabled, and reload it after updating the repository.

The companion has access only to `claude.ai` and the widget's localhost listener. It asks Claude's signed-in usage endpoint for the current session and weekly percentages; visible usage-card text remains a fallback.

## How updates work

- ChatGPT/Codex refreshes at launch and every minute through the installed desktop app's `account/rateLimits/read` service. The app handles its own authentication, so the widget does not read or store account tokens.
- Claude refreshes at launch and every 30 seconds through the Chrome companion and the existing `claude.ai` browser session. If Chrome does not deliver a response, the widget falls back to the newest plan-usage sample maintained by Claude Desktop.
- Response windows are classified by duration, so weekly-only plans and providers that reorder their returned windows do not show stale values.
- A limit omitted by the provider is displayed as unavailable instead of retaining an old percentage.

If Codex is installed somewhere other than the standard ChatGPT desktop location or your `PATH`, set `AI_USAGE_CODEX_BIN` to its executable before launching the widget.

## Project layout

- `webview_widget.py` — the Glass widget interface and local update server.
- `run-widget.sh` — the single-instance application launcher.
- `browser-companion/` — the Claude-only Chrome extension and response parser.
- `codex_usage_sync.py` — reads ChatGPT/Codex limits from the installed app's local authenticated service.
- `codex_usage_sync_test.py` — regression tests for reordered and weekly-only Codex limit responses.
- `claude_usage_sync.py` — freshness-aware fallback for Claude Desktop's local plan-usage history.
- `claude_usage_sync_test.py` — regression tests for Claude history selection and browser-data precedence.
- `install-linux-app.sh` — installs the desktop launcher and icon for the current user.

## Privacy

The Claude companion sends only the provider name, usage percentage, and displayed reset label to the local listener at `http://127.0.0.1:8765`. ChatGPT usage is read from a local Codex process. The widget does not save or send passwords, cookies, API keys, prompts, chats, or account identifiers.

## Development checks

```bash
python3 -m unittest -v codex_usage_sync_test.py claude_usage_sync_test.py
python3 -m py_compile webview_widget.py codex_usage_sync.py claude_usage_sync.py
node browser-companion/usage-parsers.test.js
for file in browser-companion/{background,content,refresh-monitor,usage-parsers}.js; do node --check "$file"; done
```

## Provider marks

The provider switch uses the official OpenAI/ChatGPT Blossom from the [OpenAI design guidelines](https://openai.com/brand/) and Claude Spark from the [Anthropic press kit](https://www.anthropic.com/press-kit). These marks belong to OpenAI and Anthropic respectively, are used only to identify the corresponding usage service, and do not imply endorsement of this project.
