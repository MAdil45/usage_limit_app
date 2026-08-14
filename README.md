# AI Usage Widget

A local Linux desktop widget for keeping ChatGPT/Codex and Claude plan limits in view. It offers two always-on-top designs:

- **Aurora** — an organic neon glass form.
- **Glass** — a frosted rounded capsule that fades its background while idle and becomes fully vivid on hover.

The widget stores its data only on the local computer in `~/.config/ai-usage-widget/usage.json`.

## What it shows

| Provider | Limits shown |
| --- | --- |
| ChatGPT / Codex | Weekly limit and reset time |
| Claude | Current 5-hour session and weekly limit, each with its own meter and reset time |

Both designs can be moved by dragging their empty header area and resized from any edge or corner.

## Requirements

The recommended widgets use GTK, WebKit, and local desktop automation. On Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0 xdotool tesseract-ocr imagemagick
```

You also need Chrome for the Claude companion extension, plus active signed-in Codex and Claude accounts.

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

Close a running widget before starting the other design. The launcher starts the Codex synchronizer with the widget and stops it when the widget closes.

Legacy prototype launchers (`run-widget.sh`, `run-aurora-glass.sh`, and `run-glass-capsule.sh`) remain in the repository for reference; use the two `*-web.sh` launchers above for the current experience.

## Automatic usage updates

### ChatGPT / Codex

When a current-style widget is open, its local synchronizer:

1. Opens **Codex Settings → Usage & billing** in the already-running Codex desktop app.
2. Reads the visible weekly remaining percentage and reset time using local OCR.
3. Restores the previously focused window.

It runs immediately at widget launch and then every 10 minutes. It stops when the widget closes. Codex must be open for this synchronizer to refresh.

### Claude

Install the included Chrome extension once:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this repository's `browser-companion` directory.
4. Keep the extension enabled. After pulling an update, use Chrome's reload button for the extension.

At widget launch, both providers refresh once. For the next 30 seconds, all periodic refreshes are suppressed so launch cannot cause duplicate work. After that quiet period, Claude refreshes every 30 seconds and ChatGPT/Codex every minute through their signed-in browser usage pages. The desktop Codex app is no longer opened or automated. The widget intentionally does not refresh on hover or model selection. Each browser page opens in an off-screen popup, sends the percentage and reset text to the local widget, then closes. If the window manager refuses off-screen placement, the extension immediately minimizes it instead. It does not refresh either provider when the widget is closed.

After updating this repository, go to `chrome://extensions` and click the extension's **Reload** button once. The new instant-Claude refresh uses Chrome's local offscreen extension page, so reload is required for a previously installed extension.

## Privacy

No passwords, cookies, API keys, prompts, chats, or account identifiers are saved or sent by this project. The Chrome companion sends only the provider name, usage percentage, and displayed reset label to the widget's local listener at `http://127.0.0.1:8765`.

The site interfaces can change. If Claude or Codex redesigns its usage screen, the text/OCR parsing may need an update.

