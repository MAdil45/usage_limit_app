#!/usr/bin/env python3
"""Use Claude Desktop's local plan history when browser sync is unavailable."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE = Path.home() / ".config" / "ai-usage-widget" / "usage.json"
HISTORY = Path.home() / ".config" / "Claude" / "plan-usage-history.json"


def latest_sample(path: Path = HISTORY) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Claude Desktop usage history is unavailable") from error
    samples = data.get("samples") if isinstance(data, dict) else None
    valid = [
        sample for sample in (samples or [])
        if isinstance(sample, dict)
        and isinstance(sample.get("t"), (int, float))
        and isinstance(sample.get("u"), dict)
    ]
    if not valid:
        raise RuntimeError("Claude Desktop usage history has no samples")
    return max(valid, key=lambda sample: sample["t"])


def normalize(sample: dict) -> tuple[dict, datetime]:
    usage = sample["u"]
    timestamp = datetime.fromtimestamp(sample["t"] / 1000, timezone.utc)
    windows = {}
    for name, key in (("5-hour", "fh"), ("Weekly", "sd")):
        value = usage.get(key)
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            windows[name] = {"used": float(value)}
    if not windows:
        raise RuntimeError("Claude Desktop usage history has no plan limits")
    return windows, timestamp


def save(windows: dict, sampled_at: datetime, state_path: Path = STATE) -> bool:
    try:
        data = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        data = {"providers": {}}
    provider = data.setdefault("providers", {}).setdefault("Claude", {"label": "Claude"})
    changed = False
    for name, values in windows.items():
        meter = provider.setdefault(name, {})
        try:
            existing = datetime.fromisoformat(meter.get("updated_at", ""))
        except (TypeError, ValueError):
            existing = None
        # A browser response includes reset labels and should win when it is
        # newer than Claude Desktop's history sample.
        if existing and existing >= sampled_at:
            continue
        meter["used"] = values["used"]
        meter["remaining"] = 100 - values["used"]
        meter.pop("unavailable", None)
        meter["reset_label"] = f"Desktop data from {sampled_at.astimezone().strftime('%a %-I:%M %p')}"
        meter["updated_at"] = sampled_at.isoformat()
        changed = True
    if changed:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(data, indent=2))
    return changed


def sync() -> tuple[dict, datetime, bool]:
    windows, sampled_at = normalize(latest_sample())
    return windows, sampled_at, save(windows, sampled_at)


if __name__ == "__main__":
    try:
        current, sampled_at, changed = sync()
        summary = ", ".join(f"{name}: {values['used']:g}% used" for name, values in current.items())
        status = "updated" if changed else "already newer"
        print(f"Claude synced ({status}, {sampled_at.astimezone():%Y-%m-%d %I:%M %p}): {summary}")
    except Exception as error:
        print(f"Claude sync skipped: {error}")
