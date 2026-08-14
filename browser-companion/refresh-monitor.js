// An offscreen document remains available while Chrome's MV3 service worker
// sleeps.  Long-polling is local-only and wakes the worker only when the user
// opens or hovers the matching provider in the desktop widget.
const REFRESH_URL = "http://127.0.0.1:8765/refresh";

async function monitor() {
  for (;;) {
    try {
      const response = await fetch(REFRESH_URL, { cache: "no-store" });
      const request = await response.json();
      if (request.provider === "Claude" || request.provider === "ChatGPT") {
        await chrome.runtime.sendMessage({ type: "refresh-request", provider: request.provider });
      }
    } catch (_) {
      // Widget not running or being restarted. Retry shortly without surfacing
      // an extension error to the user.
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

monitor();
// Chrome alarms cannot run more often than once a minute.  This persistent
// extension page sends a lightweight signal every 30 seconds instead.
setInterval(() => {
  chrome.runtime.sendMessage({ type: "periodic-refresh", provider: "Claude" }).catch(() => {});
}, 30000);
