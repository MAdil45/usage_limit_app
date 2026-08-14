#!/usr/bin/env python3
"""Native Qt previews: Aurora Glass and Glass Capsule."""
from __future__ import annotations

import argparse
import json
import queue
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt5.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ai_usage_widget import Store, time_left


PALETTES = {
    "aurora": {"ink": "#F8FBFF", "muted": "#C4D1F1", "mint": "#54F1D2", "blue": "#72A7FF", "violet": "#A87AFF", "panel": "#12193D"},
    "glass": {"ink": "#FFFFFF", "muted": "#E4ECFF", "mint": "#80F9F0", "blue": "#A7D0FF", "violet": "#D1BEFF", "panel": "#5C719D"},
}


class Receiver(BaseHTTPRequestHandler):
    events = queue.Queue()
    def _reply(self, code=200):
        self.send_response(code); self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers()
    def do_OPTIONS(self): self._reply()
    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if payload.get("provider") not in ("ChatGPT", "Claude"): raise ValueError
            Receiver.events.put(payload); self._reply()
        except (ValueError, json.JSONDecodeError): self._reply(400)
    def log_message(self, *_): pass


class UsageWidget(QWidget):
    def __init__(self, theme):
        super().__init__()
        self.theme, self.p = theme, PALETTES[theme]
        self.store, self.state, self.view = Store(), Store().load(), "ChatGPT"
        self.drag_at = None
        self.setFixedSize(420, 540)
        self.setWindowTitle(f"AI Usage — {theme.title()}")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 30, screen.top() + 36)
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(1000)

    def font(self, size, bold=False):
        f = QFont("Ubuntu", size); f.setBold(bold); return f
    def text(self, painter, rect, value, size, color=None, align=Qt.AlignLeft, bold=False):
        painter.setPen(QColor(color or self.p["ink"])); painter.setFont(self.font(size, bold)); painter.drawText(QRectF(*rect), align | Qt.AlignVCenter, value)
    def rounded(self, painter, rect, radius, fill, stroke=None, width=1):
        painter.setPen(QPen(QColor(stroke), width) if stroke else Qt.NoPen); painter.setBrush(QColor(fill)); painter.drawRoundedRect(QRectF(*rect), radius, radius)
    def paintEvent(self, _):
        q = QPainter(self); q.setRenderHint(QPainter.Antialiasing); q.setRenderHint(QPainter.TextAntialiasing)
        self.backdrop(q)
        self.draw_dashboard(q, self.view)
    def backdrop(self, q):
        if self.theme == "aurora":
            shape = QPainterPath(); shape.moveTo(65, 78); shape.cubicTo(140, 4, 228, 43, 330, 42); shape.cubicTo(405, 42, 405, 150, 384, 255); shape.cubicTo(414, 380, 353, 512, 222, 519); shape.cubicTo(90, 530, 25, 438, 39, 316); shape.cubicTo(7, 205, 29, 126, 65, 78)
            g = QLinearGradient(30, 45, 385, 510); g.setColorAt(0, QColor("#0B6E73")); g.setColorAt(.38, QColor("#16245F")); g.setColorAt(1, QColor("#5E25A0")); q.setBrush(g); q.setPen(QPen(QColor(self.p["violet"]), 2)); q.drawPath(shape)
            q.setPen(QPen(QColor(self.p["mint"]), 3)); wave = QPainterPath(); wave.moveTo(43, 403); wave.cubicTo(95, 371, 105, 437, 158, 399); wave.cubicTo(205, 367, 233, 435, 283, 390); wave.cubicTo(324, 357, 339, 402, 381, 365); q.drawPath(wave)
        else:
            # Real alpha window + layered translucent painted panels.
            self.rounded(q, (27, 22, 366, 497), 58, QColor(132, 159, 202, 155), QColor(233, 244, 255, 210), 2)
            self.rounded(q, (37, 32, 346, 477), 48, QColor(81, 106, 151, 115), QColor(213, 229, 255, 105), 1)
            glow = QLinearGradient(35, 45, 385, 485); glow.setColorAt(0, QColor(188, 223, 255, 92)); glow.setColorAt(.55, QColor(99, 124, 180, 22)); glow.setColorAt(1, QColor(172, 143, 255, 72)); q.setBrush(glow); q.setPen(Qt.NoPen); q.drawRoundedRect(QRectF(43, 38, 334, 465), 42, 42)
    def header(self, q, title, sub):
        self.text(q, (65, 63, 235, 32), title, 21, bold=True); self.text(q, (65, 94, 270, 22), sub, 10, self.p["muted"])
        self.rounded(q, (341, 54, 35, 35), 18, QColor(255,255,255,40), QColor(255,255,255,100)); self.text(q, (341, 54, 35, 35), "×", 19, align=Qt.AlignCenter)
    def card(self, q, y, title, sub, selected=False):
        fill = QColor(225, 247, 250, 225) if selected else QColor(39, 57, 103, 190)
        if self.theme == "glass": fill = QColor(224, 238, 255, 210) if selected else QColor(89, 113, 157, 165)
        self.rounded(q, (58, y, 304, 70), 28, fill, QColor(self.p["mint"]) if selected else None)
        dark = "#17233D" if selected else self.p["ink"]; muted = "#3C5477" if selected else self.p["muted"]
        self.text(q, (82, y+13, 225, 27), title, 14, dark, bold=True); self.text(q, (82, y+40, 225, 20), sub, 10, muted); self.text(q, (324, y+17, 26, 33), "›", 27, self.p["mint"] if not selected else "#1E4050", Qt.AlignCenter)
    def switcher(self, q, provider):
        self.rounded(q, (62, 139, 296, 60), 30, QColor(17, 28, 69, 145), QColor(255,255,255,72))
        left = provider == "ChatGPT"
        self.rounded(q, (66 if left else 208, 143, 150, 52), 26, QColor(238, 250, 255, 222), QColor(255,255,255,180))
        self.text(q, (83, 152, 105, 22), "✦  ChatGPT", 11, "#1B2942" if left else self.p["ink"], bold=True)
        self.text(q, (83, 172, 105, 16), "Weekly", 8, "#405271" if left else self.p["muted"])
        self.text(q, (225, 152, 100, 22), "✺  Claude", 11, self.p["ink"] if left else "#1B2942", bold=True)
        self.text(q, (225, 172, 100, 16), "5-hour + weekly", 8, self.p["muted"] if left else "#405271")
    def stat(self, q, provider, name, y):
        entry = self.state["providers"][provider][name]; used = entry.get("used")
        if not isinstance(used, (int,float)):
            remaining = entry.get("remaining")
            used = 100 - remaining if isinstance(remaining, (int, float)) else 0
        reset = entry.get("reset_label") or f"Resets in {time_left(entry['reset_at'])}"
        label = "Current session" if name == "5-hour" else "Weekly limit"
        self.text(q, (62, y, 190, 25), label, 14, bold=True); self.text(q, (62, y+26, 235, 20), reset, 10, self.p["muted"])
        self.text(q, (266, y, 92, 33), f"{used:.0f}%", 21, align=Qt.AlignRight, bold=True); self.text(q, (315, y+27, 43, 18), "used", 9, self.p["muted"], Qt.AlignRight)
        self.rounded(q, (62, y+59, 295, 13), 7, QColor(154,180,220,70)); self.rounded(q, (62, y+59, max(3, 295*min(100,max(0,used))/100), 13), 7, self.p["mint"] if name == "5-hour" else self.p["blue"])
    def draw_dashboard(self, q, provider):
        self.header(q, "AI Usage", "Your limits, beautifully in view")
        self.switcher(q, provider)
        if provider == "ChatGPT":
            entry=self.state["providers"][provider]["Weekly"]; used=entry.get("used")
            if not isinstance(used,(int,float)):
                rem=entry.get("remaining"); used=100-rem if isinstance(rem,(int,float)) else 0
            reset=entry.get("reset_label") or f"Resets in {time_left(entry['reset_at'])}"
            self.text(q,(62,218,296,23),"Weekly usage",12,self.p["muted"],Qt.AlignCenter,bold=True)
            self.text(q,(62,243,296,95),f"{used:.0f}%",64,align=Qt.AlignCenter,bold=True)
            self.text(q,(62,332,296,22),reset,11,self.p["muted"],Qt.AlignCenter)
            self.rounded(q,(62,376,296,18),9,QColor(168,190,229,72)); self.rounded(q,(62,376,max(4,296*used/100),18),9,self.p["blue"])
            self.text(q,(62,405,296,20),"of weekly allowance used",10,self.p["muted"],Qt.AlignCenter)
        else:
            self.stat(q, provider, "5-hour", 224); self.stat(q, provider, "Weekly", 358)
        self.text(q, (62, 471, 295, 20), "Local, private, and always within reach", 10, self.p["muted"], Qt.AlignCenter)
    def mousePressEvent(self, e):
        p=e.pos()
        if p.x()>330 and p.y()<100: self.close(); return
        if 135<=p.y()<=205 and 62<=p.x()<=210: self.view="ChatGPT"; self.update(); return
        if 135<=p.y()<=205 and 210<p.x()<=365: self.view="Claude"; self.update(); return
        self.drag_at = e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if self.drag_at: self.move(e.globalPos()-self.drag_at)
    def mouseReleaseEvent(self, _): self.drag_at=None
    def closeEvent(self, event):
        event.accept()
        QApplication.instance().quit()
    def poll(self):
        changed=False
        while not Receiver.events.empty():
            payload=Receiver.events.get(); provider=payload["provider"]
            for name,val in payload.get("windows",{}).items():
                if name not in self.state["providers"][provider]: continue
                if isinstance(val.get("used"),(int,float)): self.state["providers"][provider][name]["used"]=val["used"]; self.state["providers"][provider][name]["remaining"]=100-val["used"]
                if isinstance(val.get("reset_label"),str): self.state["providers"][provider][name]["reset_label"]=val["reset_label"]
                changed=True
        if changed: self.store.save(self.state); self.update()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--theme", choices=PALETTES, default="aurora"); args=parser.parse_args()
    app=QApplication([]); app.setQuitOnLastWindowClosed(True); widget=UsageWidget(args.theme)
    try: server=ThreadingHTTPServer(("127.0.0.1",8765),Receiver)
    except OSError as error: raise SystemExit(f"Close the other AI Usage widget first: {error}")
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    threading.Thread(target=server.serve_forever,daemon=True).start(); widget.show()
    try:
        app.exec_()
    finally:
        server.shutdown(); server.server_close()
if __name__=="__main__": main()
