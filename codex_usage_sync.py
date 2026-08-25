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

def read_meter(text, heading_pattern, next_heading_pattern=None):
    heading = re.search(heading_pattern, text, re.I)
    if not heading: return None
    end = len(text)
    if next_heading_pattern:
        next_heading = re.search(next_heading_pattern, text[heading.end():], re.I)
        if next_heading: end = heading.end() + next_heading.start()
    section = text[heading.start():end]
    percent = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(used|left|remaining)", section, re.I)
    if not percent: return None
    value = float(percent.group(1))
    used = 100 - value if percent.group(2).lower() in ("left", "remaining") else value
    reset = re.search(r"Resets?\s+(?:in\s+)?([^\n]+)", section, re.I)
    return {"used": used, "reset_label": f"Resets {reset.group(1).strip()}" if reset else None}

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
        session_heading = r"(?:5[\s-]*hour(?:\s+usage)?\s+limit|current\s+session)"
        weekly_heading = r"weekly(?:\s+usage)?\s+limit"
        meters = {
            "5-hour": read_meter(text, session_heading, weekly_heading),
            "Weekly": read_meter(text, weekly_heading),
        }
        if not any(meters.values()): raise RuntimeError("Could not read Codex usage limits from Usage & billing")
        try: data = json.loads(STATE.read_text())
        except (OSError, json.JSONDecodeError): data = {"providers": {}}
        provider = data.setdefault("providers", {}).setdefault("ChatGPT", {"label": "ChatGPT"})
        updated = datetime.now(timezone.utc).isoformat()
        for name, values in meters.items():
            if not values: continue
            meter = provider.setdefault(name, {})
            meter["used"], meter["remaining"] = values["used"], 100 - values["used"]
            if values["reset_label"]: meter["reset_label"] = values["reset_label"]
            meter["updated_at"] = updated
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(data, indent=2))
        summary = ", ".join(f"{name}: {values['used']:g}% used" for name, values in meters.items() if values)
        print(f"Codex synced: {summary}")
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
