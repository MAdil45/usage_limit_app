#!/usr/bin/env python3
"""A local, always-on-top usage widget for ChatGPT and Claude.

This intentionally does not ask for provider passwords, cookies, or API keys.
Consumer-plan usage is entered locally (or imported from a local companion) so
the display remains useful even when provider web interfaces change.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ai-usage-widget"
STATE_FILE = APP_DIR / "usage.json"
PROVIDERS = ("ChatGPT", "Claude")
WINDOWS = (("5-hour", 5), ("Weekly", 7 * 24))


def iso_now() -> datetime:
    return datetime.now(timezone.utc)


def default_state() -> dict:
    now = iso_now()
    return {
        "providers": {
            provider: {
                "label": provider,
                "5-hour": {"remaining": None, "reset_at": (now + timedelta(hours=5)).isoformat()},
                "Weekly": {"remaining": None, "reset_at": (now + timedelta(days=7)).isoformat()},
            }
            for provider in PROVIDERS
        }
    }


class Store:
    def load(self) -> dict:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if set(data.get("providers", {})) >= set(PROVIDERS):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return default_state()

    def save(self, state: dict) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(STATE_FILE)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def time_left(reset_at: str) -> str:
    seconds = max(0, int((parse_time(reset_at) - iso_now()).total_seconds()))
    if seconds == 0:
        return "ready now"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    prefix = f"{days}d " if days else ""
    return f"{prefix}{hours}h {minutes:02d}m"


class UsageReceiver(BaseHTTPRequestHandler):
    """Receives parsed, visible usage data from the local browser companion."""
    app = None

    def _headers(self, status=200):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_OPTIONS(self):
        self._headers()

    def do_GET(self):
        self._headers()
        self.wfile.write(b'{"service":"AI Usage Widget","status":"ready"}')

    def do_POST(self):
        if self.path != "/usage":
            self._headers(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if payload.get("provider") not in PROVIDERS or not isinstance(payload.get("windows"), dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self._headers(400)
            self.wfile.write(b'{"error":"invalid usage payload"}')
            return
        self.app.root.after(0, self.app.apply_browser_update, payload)
        self._headers()
        self.wfile.write(b'{"status":"received"}')

    def log_message(self, _format, *_args):
        pass  # Do not write account-related values to the terminal.


class EditWindow(tk.Toplevel):
    def __init__(self, app: "WidgetApp", provider: str, window_name: str):
        super().__init__(app.root)
        self.app, self.provider, self.window_name = app, provider, window_name
        entry = app.state["providers"][provider][window_name]
        self.title(f"Update {provider} {window_name}")
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        frame = ttk.Frame(self, padding=16)
        frame.grid()
        ttk.Label(frame, text=f"{provider} — {window_name}", font=("Sans", 12, "bold")).grid(columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="Remaining usage (%):").grid(row=1, column=0, sticky="w")
        self.remaining = ttk.Entry(frame, width=12)
        self.remaining.grid(row=1, column=1, padx=(12, 0))
        if entry["remaining"] is not None:
            self.remaining.insert(0, str(entry["remaining"]))
        ttk.Label(frame, text="Reset (local time):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.reset = ttk.Entry(frame, width=22)
        self.reset.grid(row=2, column=1, padx=(12, 0), pady=(10, 0))
        local = parse_time(entry["reset_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
        self.reset.insert(0, local)
        ttk.Label(frame, text="Leave usage blank if the service only shows a reset time.", foreground="#777").grid(row=3, columnspan=2, sticky="w", pady=(8, 14))
        ttk.Button(frame, text="Cancel", command=self.destroy).grid(row=4, column=0, sticky="e")
        ttk.Button(frame, text="Save", command=self.save).grid(row=4, column=1, sticky="e", padx=(8, 0))
        self.remaining.focus_set()

    def save(self) -> None:
        raw_remaining = self.remaining.get().strip()
        try:
            remaining = None if not raw_remaining else float(raw_remaining)
            if remaining is not None and not 0 <= remaining <= 100:
                raise ValueError
            local = datetime.strptime(self.reset.get().strip(), "%Y-%m-%d %H:%M").astimezone()
        except ValueError:
            messagebox.showerror("Check the values", "Usage must be 0–100 and reset time must be YYYY-MM-DD HH:MM.", parent=self)
            return
        self.app.state["providers"][self.provider][self.window_name] = {
            "remaining": remaining,
            "reset_at": local.astimezone(timezone.utc).isoformat(),
        }
        self.app.persist()
        self.destroy()


class WidgetApp:
    def __init__(self) -> None:
        self.store = Store()
        self.state = self.store.load()
        self.root = tk.Tk()
        self.root.title("AI Usage")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#15171c")
        self._build()
        self._place_top_right()
        self._tick()

    def _place_top_right(self) -> None:
        self.root.update_idletasks()
        width, height = self.root.winfo_width(), self.root.winfo_height()
        x = self.root.winfo_screenwidth() - width - 24
        self.root.geometry(f"+{x}+32")

    def _build(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background="#15171c")
        style.configure("Title.TLabel", background="#15171c", foreground="#f4f5f7", font=("Sans", 11, "bold"))
        style.configure("Text.TLabel", background="#15171c", foreground="#d7d9df", font=("Sans", 9))
        style.configure("Muted.TLabel", background="#15171c", foreground="#9298a5", font=("Sans", 8))
        style.configure("Usage.Horizontal.TProgressbar", troughcolor="#30343d", background="#69d2a3", bordercolor="#30343d", lightcolor="#69d2a3", darkcolor="#69d2a3")
        self.panel = ttk.Frame(self.root, style="Panel.TFrame", padding=13)
        self.panel.grid(sticky="nsew")
        self.show_home()

    def _clear_panel(self) -> None:
        for child in self.panel.winfo_children():
            child.destroy()

    def _header(self, title: str, back: bool = False) -> None:
        top = ttk.Frame(self.panel, style="Panel.TFrame")
        top.grid(sticky="ew", pady=(0, 10))
        if back:
            ttk.Button(top, text="Back", width=6, command=self.show_home).grid(row=0, column=0, sticky="w")
            ttk.Label(top, text=title, style="Title.TLabel").grid(row=0, column=1, sticky="w", padx=(8, 0))
        else:
            ttk.Label(top, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Menu", width=6, command=self.show_menu).grid(row=0, column=2, sticky="e", padx=(75, 0))

    def show_home(self) -> None:
        self._clear_panel()
        self.rows = []
        self._header("AI USAGE")
        ttk.Label(self.panel, text="Choose a provider", style="Text.TLabel").grid(sticky="w", pady=(3, 10))
        ttk.Button(self.panel, text="ChatGPT", width=28, command=lambda: self.show_provider("ChatGPT")).grid(sticky="ew", pady=4)
        ttk.Label(self.panel, text="Weekly usage limit", style="Muted.TLabel").grid(sticky="w", padx=10)
        ttk.Button(self.panel, text="Claude", width=28, command=lambda: self.show_provider("Claude")).grid(sticky="ew", pady=(12, 4))
        ttk.Label(self.panel, text="Current session (5-hour) and weekly limits", style="Muted.TLabel").grid(sticky="w", padx=10)
        ttk.Label(self.panel, text="Uses your signed-in browser session • localhost only", style="Muted.TLabel").grid(sticky="w", pady=(16, 0))

    def show_provider(self, provider: str) -> None:
        self._clear_panel()
        self.rows: list[tuple[str, str, ttk.Progressbar, ttk.Label]] = []
        self._header(provider, back=True)
        window_names = ("Weekly",) if provider == "ChatGPT" else ("5-hour", "Weekly")
        for window_name in window_names:
            row = ttk.Frame(self.panel, style="Panel.TFrame")
            row.grid(sticky="ew", pady=5)
            title = "Current session" if window_name == "5-hour" else "Weekly limit"
            ttk.Label(row, text=title, style="Text.TLabel", width=14).grid(row=0, column=0, sticky="w")
            bar = ttk.Progressbar(row, style="Usage.Horizontal.TProgressbar", length=120, mode="determinate", maximum=100)
            bar.grid(row=0, column=1, padx=(6, 7))
            label = ttk.Label(row, style="Muted.TLabel", width=22)
            label.grid(row=1, column=0, columnspan=2, sticky="w")
            ttk.Button(row, text="Edit", width=5, command=lambda p=provider, w=window_name: EditWindow(self, p, w)).grid(row=0, column=2, padx=(7, 0))
            self.rows.append((provider, window_name, bar, label))
        ttk.Label(self.panel, text="Updated from the corresponding web usage page", style="Muted.TLabel").grid(sticky="w", pady=(12, 0))
        self.refresh()

    def show_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Keep on top", command=lambda: self.root.attributes("-topmost", True))
        menu.add_command(label="Copy companion status", command=self.copy_companion_status)
        menu.add_command(label="Reset all windows", command=self.reset_all)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.root.destroy)
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def reset_all(self) -> None:
        self.state = default_state()
        self.persist()

    def persist(self) -> None:
        self.store.save(self.state)
        self.refresh()

    def copy_companion_status(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append("Browser companion endpoint: http://127.0.0.1:8765/usage")

    def apply_browser_update(self, payload: dict) -> None:
        provider = payload["provider"]
        for window_name, value in payload["windows"].items():
            if window_name not in self.state["providers"][provider] or not isinstance(value, dict):
                continue
            used = value.get("used")
            if isinstance(used, (int, float)) and 0 <= used <= 100:
                self.state["providers"][provider][window_name]["remaining"] = 100 - used
                self.state["providers"][provider][window_name]["used"] = used
            reset_label = value.get("reset_label")
            if isinstance(reset_label, str) and reset_label.strip():
                self.state["providers"][provider][window_name]["reset_label"] = reset_label.strip()
        self.store.save(self.state)
        self.refresh()

    def refresh(self) -> None:
        for provider, window_name, bar, label in self.rows:
            entry = self.state["providers"][provider][window_name]
            remaining = entry.get("remaining")
            bar["value"] = remaining if remaining is not None else 0
            used = entry.get("used")
            usage = f"{used:.0f}% used" if isinstance(used, (int, float)) else (f"{remaining:.0f}% left" if remaining is not None else "No usage yet")
            reset = entry.get("reset_label") or f"Resets in {time_left(entry['reset_at'])}"
            label.configure(text=f"{usage} · {reset}")

    def _tick(self) -> None:
        self.refresh()
        self.root.after(30_000, self._tick)

    def run(self) -> None:
        UsageReceiver.app = self
        self.server = ThreadingHTTPServer(("127.0.0.1", 8765), UsageReceiver)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    WidgetApp().run()
