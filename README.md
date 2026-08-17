# AI Usage Widget

A local Linux desktop widget for keeping ChatGPT/Codex and Claude plan limits in view. It offers two designs:

- **Aurora** — an organic neon glass form.
- **Glass** — a frosted rounded capsule that fades its background while idle and becomes fully vivid on hover.

The widget behaves like a normal desktop app: it comes to the front when you select it, but it does not stay above your other windows. It continues refreshing while it is in the background. Its data is stored only on the local computer in `~/.config/ai-usage-widget/usage.json`.

## What it shows

| Provider | Limits shown |
| --- | --- |
| ChatGPT / Codex | Weekly limit and reset time |
| Claude | Current 5-hour session and weekly limit, each with its own meter and reset time |

Both designs can be moved by dragging their empty header area and resized from any edge or corner.

## Requirements

The recommended widgets use GTK and WebKit. On Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

You also need Chrome for the companion extension, plus active signed-in ChatGPT/Codex and Claude accounts.

## Run

From this directory:

```bash
chmod +x run-aurora-web.sh run-glass-web.sh
./run-aurora-web.sh
```

Or launch the Glass design:

```bash
./run-glass-web.sh
```

Close a running widget before starting the other design. The current launchers refresh usage through the Chrome companion extension while the widget is open.

## Install as a Linux desktop app

Install a launcher for the current user (no `sudo` required):

```bash
./install-linux-app.sh
```

Then find **AI Usage Widget** in your Linux app launcher and open it like any other desktop app. The launcher starts the Glass design.
If the widget is already running, selecting its launcher brings that existing window to the front instead of starting a duplicate.

To uninstall the app launcher later, run:

```bash
./uninstall-linux-app.sh
```

This removes the per-user launcher and icon; it does not remove the project folder or your locally saved usage data.

Legacy prototype launchers (`run-widget.sh`, `run-aurora-glass.sh`, and `run-glass-capsule.sh`) remain in the repository for reference; use the two `*-web.sh` launchers above for the current experience.

## Automatic usage updates

Install the included Chrome extension once:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this repository's `browser-companion` directory.
4. Keep the extension enabled. After pulling an update, use Chrome's reload button for the extension.

At widget launch, both providers refresh once. For the next 30 seconds, all periodic refreshes are suppressed so launch cannot cause duplicate work. After that quiet period, Claude refreshes every 30 seconds and ChatGPT/Codex every minute through their signed-in browser usage pages. The widget intentionally does not refresh on hover or model selection. Refreshes run through the Chrome companion without automating the Codex desktop app, and they stop when the widget is closed.

After updating this repository, go to `chrome://extensions` and click the extension's **Reload** button once. The new instant-Claude refresh uses Chrome's local offscreen extension page, so reload is required for a previously installed extension.

## Privacy

No passwords, cookies, API keys, prompts, chats, or account identifiers are saved or sent by this project. The Chrome companion sends only the provider name, usage percentage, and displayed reset label to the widget's local listener at `http://127.0.0.1:8765`.

The site interfaces can change. If Claude or ChatGPT/Codex redesigns its usage screen, the usage-page parsing may need an update.
