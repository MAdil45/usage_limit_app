#!/usr/bin/env python3
"""Local-only OCR synchronizer for Codex Settings > Usage & billing."""
from __future__ import annotations

import argparse, json, re, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

STATE = Path.home() / ".config" / "ai-usage-widget" / "usage.json"

def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True).stdout.strip()

def visible_codex_window():
    ids = run("xdotool", "search", "--onlyvisible", "--name", "Codex", check=False).splitlines()
    if not ids:
        ids = run("xdotool", "search", "--onlyvisible", "--name", "ChatGPT", check=False).splitlines()
    if not ids: raise RuntimeError("Codex is not open")
    return ids[0]

def capture(window_id, path):
    run("import", "-window", window_id, path)

def ocr(path):
    return run("tesseract", path, "stdout", "--psm", "11", check=False)

def find_usage_menu_y(path):
    tsv = run("tesseract", path, "stdout", "--psm", "11", "tsv", check=False)
    words = [line.split("\t") for line in tsv.splitlines()[1:] if len(line.split("\t")) == 12]
    for i, word in enumerate(words):
        if word[11].strip().lower() == "usage":
            # The settings sidebar entry is "Usage & billing"; avoid page headings.
            near = " ".join(w[11] for w in words[i:i+3]).lower()
            if "billing" in near:
                return int(word[7]) + int(word[9]) // 2
    return None

def sync():
    previous = run("xdotool", "getactivewindow", check=False)
    codex = visible_codex_window()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            menu = f"{tmp}/menu.png"; page = f"{tmp}/page.png"
            # `windowfocus` changes input focus without asking the window
            # manager to raise or activate Codex, so it stays behind the
            # user's current app while Electron accepts the keyboard shortcut.
            run("xdotool", "windowfocus", "--sync", codex)
            run("xdotool", "key", "ctrl+comma"); time.sleep(1.4)
            capture(codex, menu)
            y = find_usage_menu_y(menu)
            if y is None: raise RuntimeError("Could not locate Usage & billing in Codex Settings")
            run("xdotool", "mousemove", "--window", codex, "112", str(y)); run("xdotool", "click", "--window", codex, "1"); time.sleep(1.6)
            capture(codex, page); text = ocr(page)
        match = re.search(r"(\d{1,3})\s*%\s*(?:left|remaining)", text, re.I)
        reset = re.search(r"Resets?\s+([^\n]+)", text, re.I)
        if not match: raise RuntimeError("Could not read Codex weekly usage from Usage & billing")
        used = 100 - int(match.group(1))
        data = json.loads(STATE.read_text())
        weekly = data["providers"]["ChatGPT"]["Weekly"]
        weekly["used"], weekly["remaining"] = used, 100 - used
        if reset: weekly["reset_label"] = f"Resets {reset.group(1).strip()}"
        weekly["updated_at"] = datetime.now(timezone.utc).isoformat()
        STATE.write_text(json.dumps(data, indent=2))
        print(f"Codex synced: {used}% used")
    finally:
        run("xdotool", "key", "Escape", check=False)
        if previous: run("xdotool", "windowfocus", "--sync", previous, check=False)

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--interval", type=int, default=600); parser.add_argument("--once", action="store_true"); args=parser.parse_args()
    while True:
        try: sync()
        except Exception as error: print(f"Codex sync skipped: {error}")
        if args.once: break
        time.sleep(max(60, args.interval))
