#!/usr/bin/env python3
"""Two visual desktop variants for the AI Usage Widget.

Run with --theme aurora or --theme glass. Both read the same local usage data
and accept the same localhost updates from the browser companion.
"""
from __future__ import annotations

import argparse
import threading
import tkinter as tk
from http.server import ThreadingHTTPServer

from ai_usage_widget import PROVIDERS, Store, UsageReceiver, time_left


THEMES = {
    "aurora": {
        "canvas": "#090b1c", "surface": "#17214c", "surface_2": "#28205b",
        "ink": "#f7f8ff", "muted": "#b7c3e5", "mint": "#52f3d3",
        "violet": "#9b67ff", "blue": "#58a9ff", "track": "#344477",
        "accent": "#79e9ff", "shape": "organic",
    },
    "glass": {
        "canvas": "#18213e", "surface": "#6276a6", "surface_2": "#8498c4",
        "ink": "#ffffff", "muted": "#e2eaff", "mint": "#80f5eb",
        "violet": "#c9b7ff", "blue": "#92c7ff", "track": "#a9bad8",
        "accent": "#d8f4ff", "shape": "capsule",
    },
}


class StyledWidget:
    WIDTH, HEIGHT = 420, 530

    def __init__(self, theme_name: str):
        self.theme_name = theme_name
        self.c = THEMES[theme_name]
        self.store = Store()
        self.state = self.store.load()
        self.view = "home"
        self.drag_anchor = None
        self.root = tk.Tk()
        self.root.title(f"AI Usage — {theme_name.title()}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # A small whole-window alpha creates a glass treatment reliably on Linux/X11.
        self.root.attributes("-alpha", 0.95 if theme_name == "aurora" else 0.88)
        self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.c["canvas"], highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.place_top_right()
        self.draw()
        self.tick()

    def place_top_right(self):
        self.root.update_idletasks()
        x = self.root.winfo_screenwidth() - self.WIDTH - 32
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+42")

    def rounded(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius,y1, x2-radius,y1, x2,y1, x2,y1+radius,
                  x2,y2-radius, x2,y2, x2-radius,y2, x1+radius,y2,
                  x1,y2, x1,y2-radius, x1,y1+radius, x1,y1]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def text(self, x, y, value, size=12, fill=None, weight="normal", anchor="w", **kwargs):
        return self.canvas.create_text(x, y, text=value, anchor=anchor,
                                       fill=fill or self.c["ink"],
                                       font=("Helvetica", size, weight), **kwargs)

    def draw_background(self):
        self.canvas.delete("all")
        if self.theme_name == "aurora":
            self.canvas.create_oval(-120, -105, 235, 205, fill="#0e766f", outline="", stipple="gray50")
            self.canvas.create_oval(180, 255, 530, 625, fill="#6f33c4", outline="", stipple="gray50")
            self.rounded(18, 18, 402, 512, 70, fill=self.c["surface"], outline=self.c["violet"], width=2)
            self.canvas.create_line(40, 420, 115, 397, 184, 426, 255, 386, 326, 418, 381, 375,
                                    fill=self.c["mint"], width=3, smooth=True)
        else:
            # Layered translucent-looking panes make a frosted capsule without external packages.
            self.rounded(18, 18, 402, 512, 54, fill="#8095c4", outline="#eaf4ff", width=2, stipple="gray50")
            self.rounded(28, 29, 392, 502, 46, fill=self.c["surface"], outline="#bfd3ff", width=1, stipple="gray75")
            self.canvas.create_oval(260, 40, 465, 220, fill="#a4ddff", outline="", stipple="gray50")
            self.canvas.create_oval(-75, 315, 170, 570, fill="#a58eff", outline="", stipple="gray50")

    def header(self, title, subtitle):
        self.text(55, 67, title, 21, weight="bold")
        self.text(56, 94, subtitle, 10, self.c["muted"])
        self.rounded(340, 46, 372, 78, 16, fill="#ffffff", outline="", stipple="gray50", tags="close")
        self.text(356, 62, "×", 19, self.c["ink"], anchor="center")
        self.canvas.tag_bind("close", "<Button-1>", lambda _event: self.root.destroy())

    def button(self, y, title, caption, action, selected=False):
        fill = "#d9f9f5" if selected else "#273763"
        if self.theme_name == "glass":
            fill = "#d7e5fa" if selected else "#5e719e"
        tag = f"button:{action}"
        self.rounded(54, y, 366, y+70, 28, fill=fill, outline=self.c["accent"] if selected else "", width=1, tags=tag)
        self.text(78, y+26, title, 14, "#16213a" if selected else self.c["ink"], "bold", tags=tag)
        self.text(78, y+48, caption, 10, "#385073" if selected else self.c["muted"], tags=tag)
        self.text(340, y+35, "›", 25, "#18213b" if selected else self.c["accent"], anchor="center", tags=tag)
        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, target=action: self.navigate(target))

    def draw_home(self):
        self.header("AI Usage", "A little clarity for your creative flow")
        self.text(55, 145, "Choose your space", 12, self.c["muted"], "bold")
        self.button(170, "ChatGPT", "Weekly usage, reset and availability", "ChatGPT")
        self.button(258, "Claude", "5-hour session and weekly limits", "Claude")
        self.rounded(55, 377, 366, 441, 26, fill="#101733", outline="", stipple="gray50")
        self.text(76, 402, "Live when your browser usage page is open", 11, self.c["ink"], "bold")
        self.text(76, 424, "Updates stay on this computer", 10, self.c["muted"])
        self.text(210, 477, "Drag me anywhere", 10, self.c["muted"], anchor="center")

    def usage(self, provider, window_name, y):
        entry = self.state["providers"][provider][window_name]
        used = entry.get("used")
        if not isinstance(used, (int, float)):
            used = 100 - entry["remaining"] if entry.get("remaining") is not None else 0
        reset = entry.get("reset_label") or f"Resets in {time_left(entry['reset_at'])}"
        title = "Current session" if window_name == "5-hour" else "Weekly limit"
        self.text(56, y, title, 13, weight="bold")
        self.text(56, y+23, reset, 10, self.c["muted"])
        self.text(362, y+9, f"{used:.0f}%", 20, self.c["ink"], "bold", anchor="e")
        self.text(362, y+29, "used", 9, self.c["muted"], anchor="e")
        self.rounded(56, y+48, 364, y+62, 7, fill=self.c["track"], outline="")
        width = 308 * max(0, min(100, used)) / 100
        if width:
            self.rounded(56, y+48, 56+width, y+62, 7, fill=self.c["mint"] if window_name == "5-hour" else self.c["blue"], outline="")

    def draw_provider(self, provider):
        self.header(provider, "Tap the provider name below to return")
        back_tag = "back"
        self.rounded(54, 121, 144, 153, 16, fill="#ffffff", outline="", stipple="gray50", tags=back_tag)
        self.text(99, 137, "‹  all", 11, self.c["ink"], "bold", anchor="center", tags=back_tag)
        self.canvas.tag_bind(back_tag, "<Button-1>", lambda _event: self.navigate("home"))
        self.usage(provider, "Weekly", 205 if provider == "ChatGPT" else 282)
        if provider == "Claude":
            self.usage(provider, "5-hour", 185)
            self.rounded(55, 381, 365, 432, 22, fill="#101733", outline="", stipple="gray50")
            self.text(76, 402, "Claude limits refresh from its web usage page", 10, self.c["muted"])
        else:
            self.rounded(55, 315, 365, 379, 22, fill="#101733", outline="", stipple="gray50")
            self.text(76, 339, "Your weekly allowance", 11, self.c["ink"], "bold")
            self.text(76, 361, "Synced from ChatGPT/Codex usage & billing", 10, self.c["muted"])

    def draw(self):
        self.draw_background()
        if self.view == "home":
            self.draw_home()
        else:
            self.draw_provider(self.view)

    def navigate(self, target):
        self.view = target
        self.draw()

    def start_drag(self, event):
        # Tags with controls handle their own click. Empty space begins a window drag.
        if not self.canvas.gettags("current"):
            self.drag_anchor = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def drag(self, event):
        if self.drag_anchor:
            x0, y0, window_x, window_y = self.drag_anchor
            self.root.geometry(f"+{window_x + event.x_root - x0}+{window_y + event.y_root - y0}")

    def stop_drag(self, _event):
        self.drag_anchor = None

    def apply_browser_update(self, payload):
        provider = payload["provider"]
        for window_name, value in payload["windows"].items():
            if window_name not in self.state["providers"][provider] or not isinstance(value, dict):
                continue
            used = value.get("used")
            if isinstance(used, (int, float)) and 0 <= used <= 100:
                self.state["providers"][provider][window_name]["remaining"] = 100 - used
                self.state["providers"][provider][window_name]["used"] = used
            if isinstance(value.get("reset_label"), str):
                self.state["providers"][provider][window_name]["reset_label"] = value["reset_label"]
        self.store.save(self.state)
        self.draw()

    def tick(self):
        self.draw()
        self.root.after(30_000, self.tick)

    def run(self):
        UsageReceiver.app = self
        server = ThreadingHTTPServer(("127.0.0.1", 8765), UsageReceiver)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=THEMES, default="aurora")
    args = parser.parse_args()
    StyledWidget(args.theme).run()
