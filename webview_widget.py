#!/usr/bin/env python3
"""High-fidelity Aurora and Glass desktop widgets using native WebKit CSS."""
from __future__ import annotations
import argparse, json, queue, subprocess, sys, threading, time, warnings
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0'); gi.require_version('WebKit2', '4.0')
from gi.repository import Gdk, GLib, Gtk, WebKit2

STATE = Path.home() / '.config' / 'ai-usage-widget' / 'usage.json'
EVENTS = queue.Queue()
REFRESHES = queue.Queue()
REFRESH_CONDITION = threading.Condition()
STARTED_AT = time.monotonic()
STARTUP_QUIET_SECONDS = 30
# Glass-only idle background strength: 0.0 = invisible, 1.0 = fully opaque.
# Change this number, save, and restart the Glass widget to try a new value.
GLASS_IDLE_OPACITY = 0.35
warnings.filterwarnings('ignore', category=DeprecationWarning, message='WebKit2.WebView.run_javascript is deprecated')

def periodic_refresh_allowed():
    return time.monotonic() - STARTED_AT >= STARTUP_QUIET_SECONDS

def request_provider_refresh(provider, force=False):
    if not force and not periodic_refresh_allowed(): return False
    REFRESHES.put(provider)
    with REFRESH_CONDITION: REFRESH_CONDITION.notify_all()
    return True

class Receiver(BaseHTTPRequestHandler):
    def _reply(self, status=200):
        self.send_response(status); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def do_OPTIONS(self): self._reply()
    def _write(self, value):
        try: self.wfile.write(value)
        # The extension cancels its local long-poll while Chrome suspends or
        # reloads it.  That is normal and must not create a server traceback.
        except (BrokenPipeError, ConnectionResetError): pass
    def do_GET(self):
        if self.path == '/status':
            self._reply(); self._write(json.dumps({"widget":"running", "periodic_refresh_allowed":periodic_refresh_allowed()}).encode())
        elif self.path.startswith('/refresh'):
            # The extension's offscreen page long-polls this endpoint, which
            # gives a selected provider an immediate refresh without relying on
            # Chrome's one-minute alarm granularity.
            with REFRESH_CONDITION:
                if REFRESHES.empty(): REFRESH_CONDITION.wait(timeout=25)
                try: provider = REFRESHES.get_nowait()
                except queue.Empty: provider = None
            self._reply(); self._write(json.dumps({"provider": provider}).encode())
        else: self._reply(404)
    def do_POST(self):
        try:
            payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            provider = payload.get('provider')
            if provider not in ('ChatGPT','Claude'): raise ValueError
            if payload.get('action') == 'refresh':
                request_provider_refresh(provider)
            else: EVENTS.put(payload)
            self._reply()
        except (ValueError, json.JSONDecodeError): self._reply(400)
    def log_message(self, *_): pass

def html(theme):
    aurora = theme == 'aurora'
    shape = 'aurora' if aurora else 'glass'
    page = f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}} html,body{{margin:0;width:100%;height:100%;background:transparent;overflow:hidden;font-family:Inter,Ubuntu,Arial,sans-serif;color:#f8fbff;user-select:none}}
body{{display:flex;align-items:center;justify-content:center}} .shell{{position:relative;width:calc(100% - 36px);height:calc(100% - 40px);min-width:330px;min-height:460px;overflow:hidden;background:rgba(14,25,72,.76);border:0;box-shadow:0 22px 70px rgba(4,7,35,.55);backdrop-filter:blur(30px) saturate(145%)}}
.glass{{border-radius:58px;background:transparent;--glass-idle:{GLASS_IDLE_OPACITY};}} .glass::before{{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;background:linear-gradient(150deg,rgba(151,185,228,.58),rgba(55,83,142,.46) 55%,rgba(133,105,192,.5));opacity:var(--glass-idle);transition:opacity .28s ease-in-out;}} .glass:hover::before,.glass:focus-within::before{{opacity:1}} .aurora{{border-radius:38% 48% 42% 44% / 32% 31% 46% 44%;background:radial-gradient(circle at 8% 26%,rgba(45,246,207,.68),transparent 32%),radial-gradient(circle at 93% 75%,rgba(190,71,255,.75),transparent 37%),linear-gradient(145deg,rgba(10,80,118,.88),rgba(25,19,82,.92) 53%,rgba(83,27,145,.9));border-color:rgba(128,229,255,.8)}}
.shine{{position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,.22),transparent 26%,transparent 68%,rgba(181,132,255,.18));pointer-events:none}} .aurora .shine{{background:radial-gradient(ellipse at 17% 15%,rgba(255,255,255,.2),transparent 28%),linear-gradient(125deg,transparent 45%,rgba(139,84,255,.22))}}
.top{{position:absolute;top:31px;left:46px;right:42px;text-align:center}} h1{{font-size:22px;margin:0;font-weight:700;letter-spacing:-.5px}} .close{{position:absolute;right:0;top:-5px;width:40px;height:40px;border-radius:50%;border:1px solid rgba(255,255,255,.38);background:rgba(255,255,255,.14);color:white;font-size:28px;line-height:35px;cursor:pointer}}
.switch{{position:absolute;left:46px;right:46px;top:142px;height:62px;border-radius:31px;padding:4px;display:flex;background:rgba(8,19,61,.42);border:1px solid rgba(255,255,255,.25)}} .choice{{border:0;background:transparent;color:#f5f7ff;flex:1;border-radius:27px;text-align:left;padding:9px 13px;line-height:17px;cursor:pointer;font-size:12px;white-space:nowrap}} .choice b{{font-size:13px;display:block}} .choice.active{{background:linear-gradient(135deg,#f7ffff,#cfeafa);color:#17263d;box-shadow:0 3px 13px rgba(5,10,45,.24)}}
.main{{position:absolute;top:226px;left:46px;right:46px;text-align:center}} .eyebrow{{font-size:13px;font-weight:650;color:#d7e7ff}} .percent{{font-size:76px;line-height:82px;letter-spacing:-5px;font-weight:760;margin-top:2px;text-shadow:0 3px 12px rgba(0,0,0,.18)}} .reset{{font-size:13px;color:#d8e6ff;margin-top:4px}} .bar{{margin-top:25px;height:18px;border-radius:12px;background:rgba(196,219,251,.27);box-shadow:inset 0 1px 5px rgba(8,13,55,.28);overflow:hidden}} .fill{{height:100%;width:0%;border-radius:inherit;background:linear-gradient(90deg,#68e9ff,#7a9eff);box-shadow:0 0 14px rgba(85,238,255,.6);transition:width .55s ease}} .caption{{font-size:12px;color:#dce8ff;margin-top:12px}} .updated{{position:absolute;bottom:38px;left:30px;right:30px;text-align:center;font-size:11px;color:#d8e9ff;opacity:.85}} .weekly{{display:none;margin-top:17px;padding-top:11px;border-top:1px solid rgba(255,255,255,.25);text-align:left}} .weekly-head{{display:flex;justify-content:space-between;font-size:12px;color:#e1edff}} .weekly-head b{{font-size:15px;color:#fff}} .weekly .bar{{height:10px;margin-top:8px}} .claude-mode .percent{{font-size:58px;line-height:63px}} .claude-mode .bar{{margin-top:17px}} .claude-mode .weekly{{display:block}} .claude-mode .wave{{display:none}}
.aurora .wave{{display:block}} .wave{{display:none;position:absolute;left:18px;right:16px;bottom:89px;height:54px;opacity:.94}} .glass .percent{{text-shadow:0 3px 20px rgba(18,34,82,.5)}} .glass .bar{{background:rgba(243,244,255,.3)}} .grip{{position:absolute;right:12px;bottom:10px;width:28px;height:28px;opacity:.82;background:repeating-linear-gradient(135deg,transparent 0 6px,rgba(255,255,255,.78) 6px 7px);border-radius:4px;pointer-events:none}}
/* Pull the navigation upward so Claude's two usage meters breathe. */
 .switch{{top:96px}} .main{{top:186px}} .claude-mode .main{{top:178px}} .claude-mode .weekly{{margin-top:13px;padding-top:9px}} .claude-mode .weekly .bar{{margin-top:6px}}
@media (max-height:490px){{.top{{top:22px;left:34px;right:32px}}.switch{{top:78px;left:34px;right:34px;height:56px}}.main,.claude-mode .main{{top:150px;left:34px;right:34px}}.percent{{font-size:64px;line-height:68px}}.claude-mode .percent{{font-size:50px;line-height:54px}}.bar{{margin-top:14px}}.updated{{bottom:26px}}}}
</style></head><body><div id="shell" class="shell {shape}"><div class="shine"></div><div class="top"><h1>AI Usage</h1><button class="close" onclick="document.title='close'">×</button></div><div class="switch"><button id="chat" class="choice active" onclick="pick('ChatGPT')"><b>✦ ChatGPT</b>Weekly</button><button id="claude" class="choice" onclick="pick('Claude')"><b>✺ Claude</b>5-hour + weekly</button></div><div class="main"><div id="eyebrow" class="eyebrow">Weekly usage</div><div id="percent" class="percent">—</div><div id="reset" class="reset">Waiting for sync</div><div class="bar"><div id="fill" class="fill"></div></div><div id="caption" class="caption">of weekly allowance used</div><div id="weekly" class="weekly"><div class="weekly-head"><span>Weekly limit</span><b id="weekly-used">—</b></div><div id="weekly-reset" class="reset">Waiting for sync</div><div class="bar"><div id="weekly-fill" class="fill"></div></div></div></div><svg class="wave" viewBox="0 0 350 54" preserveAspectRatio="none"><path d="M0,34 C35,15 58,49 98,29 S154,51 201,20 S276,43 350,8" fill="none" stroke="#5bf4e1" stroke-width="3"/></svg><div id="updated" class="updated">Local • private • always in reach</div><div class="grip"></div></div><script>let provider='ChatGPT',lastRequested={{}},refreshing=null;function requestRefresh(p){{let now=Date.now();if(now-(lastRequested[p]||0)<5000)return;lastRequested[p]=now;refreshing={{provider:p,started:now}};document.getElementById('updated').textContent='Refreshing '+p+'…';document.title='refresh:'+p+':'+now}}function pick(p){{provider=p;document.getElementById('chat').classList.toggle('active',p==='ChatGPT');document.getElementById('claude').classList.toggle('active',p==='Claude');render(window.data||{{}});requestRefresh(p)}}function pct(e){{return Number.isFinite(e?.used)?e.used:(Number.isFinite(e?.remaining)?100-e.remaining:null)}}function render(d){{window.data=d;let w=d?.providers?.[provider]||{{}};let e=w[provider==='Claude'?'5-hour':'Weekly']||{{}};let used=pct(e);if(refreshing?.provider===provider&&Date.parse(e.updated_at||'')>=refreshing.started)refreshing=null;document.getElementById('shell').classList.toggle('claude-mode',provider==='Claude');document.getElementById('eyebrow').textContent=provider==='Claude'?'Current session':'Weekly usage';document.getElementById('percent').textContent=used===null?'—':Math.round(used)+'%';document.getElementById('fill').style.width=(used||0)+'%';document.getElementById('reset').textContent=e.reset_label||'Waiting for sync';document.getElementById('caption').textContent=provider==='Claude'?'of 5-hour session used':'of weekly allowance used';let weekly=w['Weekly']||{{}};let wu=pct(weekly);document.getElementById('weekly-used').textContent=wu===null?'—':Math.round(wu)+'% used';document.getElementById('weekly-reset').textContent=weekly.reset_label||'Waiting for sync';document.getElementById('weekly-fill').style.width=(wu||0)+'%';document.getElementById('updated').textContent=refreshing?.provider===provider?'Refreshing '+provider+'…':e.updated_at?'Last updated '+new Date(e.updated_at).toLocaleTimeString():'Local • private • always in reach'}};document.getElementById('shell').addEventListener('mouseenter',()=>requestRefresh(provider));document.addEventListener('mousedown',e=>{{if(e.button!==0||e.target.closest('button'))return;const m=16,x=e.clientX,y=e.clientY,w=innerWidth,h=innerHeight;let edge='';if(y<m)edge+='N';else if(y>h-m)edge+='S';if(x<m)edge+=edge?'_W':'W';else if(x>w-m)edge+=edge?'_E':'E';if(edge){{e.preventDefault();document.title=`resize:${{edge}}:${{Math.round(e.screenX)}}:${{Math.round(e.screenY)}}`;}}else if(y<130){{e.preventDefault();document.title=`move:0:${{edge}}:${{Math.round(e.screenX)}}:${{Math.round(e.screenY)}}`;}}}},true);</script></body></html>'''

    # WebKit consumes ordinary GTK mouse events. This capture listener forwards
    # header drags and every window edge/corner to the native GTK window.
    return page.replace('</body></html>', '''<script>
window.addEventListener('mousedown', function (event) {
  if (event.button !== 0 || event.target.closest('button')) return;
  const margin = 16, x = event.clientX, y = event.clientY;
  const vertical = y < margin ? 'NORTH' : y > innerHeight - margin ? 'SOUTH' : '';
  const horizontal = x < margin ? 'WEST' : x > innerWidth - margin ? 'EAST' : '';
  const edge = vertical && horizontal ? vertical + '_' + horizontal : vertical || horizontal;
  if (edge) {
    event.preventDefault(); event.stopPropagation();
    document.title = 'resize:' + edge + ':' + Math.round(event.screenX) + ':' + Math.round(event.screenY);
  } else if (y < 82) {
    event.preventDefault(); event.stopPropagation();
    document.title = 'move:0:' + Math.round(event.screenX) + ':' + Math.round(event.screenY);
  }
}, true);
const tabs = document.querySelector('.switch');
tabs.addEventListener('click', function (event) {
  const bounds = tabs.getBoundingClientRect();
  pick(event.clientX < bounds.left + bounds.width / 2 ? 'ChatGPT' : 'Claude');
});
document.addEventListener('mousemove', function (event) {
  const margin = 16, x = event.clientX, y = event.clientY;
  const vertical = y < margin ? 'n' : y > innerHeight - margin ? 's' : '';
  const horizontal = x < margin ? 'w' : x > innerWidth - margin ? 'e' : '';
  const cursor = vertical && horizontal ? (vertical === horizontal ? 'nwse-resize' : 'nesw-resize') : vertical ? vertical + 's-resize' : horizontal ? horizontal + 'w-resize' : 'default';
  document.body.style.cursor = cursor;
}, true);
// Refreshing is scheduled in the extension (launch, 30-second Claude cycle,
// and 60-second ChatGPT cycle). Do not trigger more work merely on hover or
// model selection.
requestRefresh = function () {};
</script></body></html>''')

class App:
    def __init__(self, theme):
        self.window=Gtk.Window(); self.window.set_decorated(False); self.window.set_keep_above(True); self.window.set_default_size(420,540); self.window.set_resizable(True); self.window.set_size_request(330,440); self.window.set_app_paintable(True)
        screen=self.window.get_screen(); self.window.set_visual(screen.get_rgba_visual())
        # Keep the native container transparent; only the HTML glass shell paints.
        native_css = Gtk.CssProvider()
        native_css.load_from_data(b'window, webview, webkitwebview { background-color: rgba(0, 0, 0, 0); }')
        Gtk.StyleContext.add_provider_for_screen(screen, native_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.codex_refresh_running=False
        self.web=WebKit2.WebView(); self.web.set_background_color(Gdk.RGBA(0,0,0,0)); self.web.add_events(Gdk.EventMask.BUTTON_PRESS_MASK); self.window.add(self.web); self.web.connect('notify::title',self.title); self.web.connect('button-press-event',self.press); self.window.connect('destroy',Gtk.main_quit)
        self.web.load_html(html(theme), 'file:///'); self.window.show_all(); GLib.timeout_add(1000,self.tick); GLib.idle_add(self.startup_refresh)
    def startup_refresh(self):
        # Sync both providers once at launch.  Further hover/click/alarm syncs
        # are deliberately ignored for 30 seconds to avoid duplicate refreshes.
        request_provider_refresh('Claude', force=True); request_provider_refresh('ChatGPT', force=True)
        return False
    def title(self, view, _):
        title = view.get_title() or ''
        if title == 'close':
            self.window.destroy(); return
        action, _, values = title.partition(':')
        if action == 'refresh':
            provider = values.split(':', 1)[0]
            request_provider_refresh(provider)
            return
        if action not in ('move', 'resize') or not values: return
        try:
            edge, x, y = values.split(':')
            stamp = Gtk.get_current_event_time() or Gdk.CURRENT_TIME
            if action == 'move':
                self.window.begin_move_drag(1, int(x), int(y), stamp)
            else:
                edges = {name: getattr(Gdk.WindowEdge, name) for name in ('NORTH','SOUTH','EAST','WEST','NORTH_EAST','NORTH_WEST','SOUTH_EAST','SOUTH_WEST')}
                self.window.begin_resize_drag(edges[edge], 1, int(x), int(y), stamp)
        except (KeyError, ValueError):
            pass
    def press(self, widget, event):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        if event.button != 1: return False
        edge = 12
        if event.x <= edge or event.x >= width-edge or event.y <= edge or event.y >= height-edge:
            horizontal = 'WEST' if event.x <= edge else 'EAST'
            vertical = 'NORTH' if event.y <= edge else 'SOUTH'
            if event.x <= edge and event.y <= edge: resize_edge = Gdk.WindowEdge.NORTH_WEST
            elif event.x >= width-edge and event.y <= edge: resize_edge = Gdk.WindowEdge.NORTH_EAST
            elif event.x <= edge and event.y >= height-edge: resize_edge = Gdk.WindowEdge.SOUTH_WEST
            elif event.x >= width-edge and event.y >= height-edge: resize_edge = Gdk.WindowEdge.SOUTH_EAST
            elif event.x <= edge: resize_edge = Gdk.WindowEdge.WEST
            elif event.x >= width-edge: resize_edge = Gdk.WindowEdge.EAST
            elif event.y <= edge: resize_edge = Gdk.WindowEdge.NORTH
            else: resize_edge = Gdk.WindowEdge.SOUTH
            self.window.begin_resize_drag(resize_edge, event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        # Header/empty surface drags the widget; controls below remain clickable.
        if event.y < 126 and not (event.x > width - 92 and event.y < 105):
            self.window.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False
    def tick(self):
        changed=False
        while not EVENTS.empty():
            p=EVENTS.get()
            if p.get('action') == 'refresh-codex':
                self.refresh_codex(); continue
            data=json.loads(STATE.read_text()); provider=p['provider']
            provider_changed=False
            for name,val in p.get('windows',{}).items():
                if name not in data['providers'][provider]: continue
                if isinstance(val.get('used'),(int,float)): data['providers'][provider][name]['used']=val['used'];data['providers'][provider][name]['remaining']=100-val['used'];provider_changed=True
                if isinstance(val.get('reset_label'),str): data['providers'][provider][name]['reset_label']=val['reset_label'];provider_changed=True
            if provider_changed:
                for meter in data['providers'][provider].values():
                    if isinstance(meter, dict): meter['updated_at']=datetime.now(timezone.utc).isoformat()
            STATE.write_text(json.dumps(data,indent=2)); changed=True
        try: data=STATE.read_text()
        except OSError: data='{}'
        self.web.run_javascript('render('+data+')',None,None,None)
        return True
    def refresh_codex(self):
        if self.codex_refresh_running: return
        self.codex_refresh_running=True
        def run_refresh():
            try: subprocess.run([sys.executable, str(Path(__file__).with_name('codex_usage_sync.py')), '--once'], check=False)
            finally: self.codex_refresh_running=False
        threading.Thread(target=run_refresh, daemon=True).start()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--theme',choices=['aurora','glass'],default='aurora');args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',8765),Receiver);threading.Thread(target=server.serve_forever,daemon=True).start();App(args.theme);Gtk.main()
