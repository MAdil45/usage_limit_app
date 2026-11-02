#!/usr/bin/env python3
"""Synchronize ChatGPT/Codex plan limits through the local Codex app server."""
from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

STATE = Path.home() / ".config" / "ai-usage-widget" / "usage.json"
DEFAULT_CODEX = Path("/usr/lib/chatgpt/resources/codex")


def codex_executable() -> str:
    configured = os.environ.get("AI_USAGE_CODEX_BIN")
    if configured:
        return configured
    if DEFAULT_CODEX.is_file():
        return str(DEFAULT_CODEX)
    found = shutil.which("codex")
    if found:
        return found
    raise RuntimeError("Codex executable was not found")


def send(process: subprocess.Popen, message: dict) -> None:
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


def response(process: subprocess.Popen, request_id: int, timeout: float = 20) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], min(0.5, deadline - time.monotonic()))
        if not ready:
            if process.poll() is not None:
                raise RuntimeError("Codex app server exited before replying")
            continue
        line = process.stdout.readline()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if message.get("error"):
            raise RuntimeError(str(message["error"]))
        return message.get("result") or {}
    raise RuntimeError("Codex usage request timed out")


def read_rate_limits() -> dict:
    process = subprocess.Popen(
        [codex_executable(), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        send(process, {
            "method": "initialize", "id": 1,
            "params": {"clientInfo": {"name": "ai-usage-widget", "title": "AI Usage Widget", "version": "0.4.1"}}
        })
        response(process, 1)
        send(process, {"method": "initialized", "params": {}})
        send(process, {"method": "account/rateLimits/read", "id": 2, "params": {}})
        return response(process, 2)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def first_value(mapping: dict, *names):
    for name in names:
        if mapping.get(name) is not None:
            return mapping[name]
    return None


def main_snapshot(result: dict) -> dict:
    snapshot = result.get("rateLimits") or result.get("rate_limits")
    if isinstance(snapshot, dict):
        return snapshot
    by_id = result.get("rateLimitsByLimitId") or result.get("rate_limits_by_limit_id") or {}
    for preferred in ("codex", "chatgpt"):
        if isinstance(by_id.get(preferred), dict):
            return by_id[preferred]
    return next((item for item in by_id.values() if isinstance(item, dict)), {})


def normalize_window(window: dict | None) -> dict | None:
    if not isinstance(window, dict):
        return None
    used = first_value(window, "usedPercent", "used_percent")
    minutes = first_value(window, "windowDurationMins", "window_minutes")
    resets_at = first_value(window, "resetsAt", "resets_at")
    if not isinstance(used, (int, float)):
        return None
    label = None
    if isinstance(resets_at, (int, float)):
        reset = datetime.fromtimestamp(resets_at).astimezone()
        if isinstance(minutes, (int, float)) and minutes >= 2 * 24 * 60:
            label = f"Resets {reset.strftime('%b %-d, %Y %-I:%M %p')}"
        else:
            label = f"Resets {reset.strftime('%-I:%M %p')}"
    return {"used": float(used), "minutes": minutes, "reset_label": label}


def classify_windows(result: dict) -> dict:
    snapshot = main_snapshot(result)
    candidates = [
        normalize_window(snapshot.get("primary")),
        normalize_window(snapshot.get("secondary")),
        normalize_window(snapshot.get("primary_window")),
        normalize_window(snapshot.get("secondary_window")),
    ]
    windows = {"5-hour": {"unavailable": True}, "Weekly": {"unavailable": True}}
    for candidate in (item for item in candidates if item):
        minutes = candidate.pop("minutes", None)
        name = "Weekly" if isinstance(minutes, (int, float)) and minutes >= 2 * 24 * 60 else "5-hour"
        windows[name] = candidate
    if all(item.get("unavailable") for item in windows.values()):
        raise RuntimeError("Codex returned no plan usage windows")
    return windows


def save(windows: dict) -> None:
    try:
        data = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        data = {"providers": {}}
    provider = data.setdefault("providers", {}).setdefault("ChatGPT", {"label": "ChatGPT"})
    updated = datetime.now(timezone.utc).isoformat()
    for name, values in windows.items():
        meter = provider.setdefault(name, {})
        if values.get("unavailable"):
            for field in ("used", "remaining", "reset_label", "reset_at"):
                meter.pop(field, None)
            meter["unavailable"] = True
        else:
            meter.pop("unavailable", None)
            meter.pop("reset_at", None)
            meter["used"] = values["used"]
            meter["remaining"] = 100 - values["used"]
            if values.get("reset_label"):
                meter["reset_label"] = values["reset_label"]
        meter["updated_at"] = updated
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2))


def sync() -> dict:
    windows = classify_windows(read_rate_limits())
    save(windows)
    return windows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            current = sync()
            summary = ", ".join(
                f"{name}: {values['used']:g}% used"
                for name, values in current.items() if "used" in values
            )
            print(f"ChatGPT synced: {summary}")
        except Exception as error:
            print(f"ChatGPT sync skipped: {error}")
        if args.once:
            break
        time.sleep(max(30, args.interval))
