// Opens signed-in usage pages in a minimized Chrome popup and forwards only
// usage percentages/reset labels to the desktop widget's localhost listener.
const LOCAL_RECEIVER = "http://127.0.0.1:8765/usage";
const USAGE_URLS = {
  Claude: "https://claude.ai/settings/usage",
  ChatGPT: "https://chatgpt.com/codex/settings/usage"
};
const OFFSCREEN_PATH = "refresh-monitor.html";
const CHATGPT_ALARM = "chatgpt-usage-refresh";
let pendingTabId = null;
let pendingWindowId = null;
let pendingProvider = null;
let creatingWindow = false;
const queuedProviders = new Set();
const FALLBACK_CLOSE_MS = { Claude: 30000, ChatGPT: 8000 };

async function widgetStatus() {
  try {
    const response = await fetch("http://127.0.0.1:8765/status", { cache: "no-store" });
    return response.ok ? await response.json() : null;
  } catch (_) {
    return null;
  }
}

async function closePendingWindow() {
  const windowId = pendingWindowId;
  pendingTabId = null; pendingWindowId = null; pendingProvider = null;
  if (windowId !== null) try { await chrome.windows.remove(windowId); } catch (_) {}
  drainRefreshQueue(true).catch(() => {});
}

function scheduleFallbackClose(tabId, windowId, provider) {
  setTimeout(() => {
    if (pendingTabId === tabId && pendingWindowId === windowId) closePendingWindow();
  }, FALLBACK_CLOSE_MS[provider]);
}

async function drainRefreshQueue(force = false) {
  if (pendingTabId !== null || creatingWindow || queuedProviders.size === 0) return;
  creatingWindow = true;
  const provider = queuedProviders.values().next().value;
  queuedProviders.delete(provider);
  try {
    const status = await widgetStatus();
    if (!status || (!force && !status.periodic_refresh_allowed)) return;
    // This is deliberately minimized instead of positioned off-screen: Chrome
    // rejects off-screen bounds on Linux and a background tab may create a
    // visible normal Chrome window when no browser window is available.
    const backgroundWindow = await chrome.windows.create({
      url: USAGE_URLS[provider], type: "popup", state: "minimized", focused: false
    });
    const tabs = await chrome.tabs.query({ windowId: backgroundWindow.id });
    if (!tabs[0]) {
      await chrome.windows.remove(backgroundWindow.id);
      throw new Error("Chrome created a usage window without a tab");
    }
    pendingProvider = provider;
    pendingWindowId = backgroundWindow.id;
    pendingTabId = tabs[0].id;
    // A cached page can complete before `tabs.query` returns. Schedule the
    // fallback here (not only in onUpdated) so it never blocks the queue.
    scheduleFallbackClose(pendingTabId, pendingWindowId, provider);
  } catch (error) {
    // Do not lose a scheduled provider refresh because Chrome was starting,
    // the network was briefly unavailable, or a tab failed to initialize.
    console.warn("Usage refresh failed; retrying", provider, error);
    queuedProviders.add(provider);
    setTimeout(() => drainRefreshQueue(force).catch(() => {}), 5000);
  } finally {
    creatingWindow = false;
  }
}

function requestRefresh(provider, force = false) {
  if (!USAGE_URLS[provider]) return false;
  queuedProviders.add(provider);
  drainRefreshQueue(force).catch(() => {});
  return true;
}

async function ensureRefreshMonitor() {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_PATH,
    reasons: ["DOM_SCRAPING"],
    justification: "Receive local widget refresh requests without waiting for Chrome's alarm interval."
  });
}

function installPeriodicRefresh() {
  // Chrome alarms cannot run faster than once a minute. The offscreen page
  // handles Claude every 30 seconds; this alarm refreshes ChatGPT every minute.
  chrome.alarms.create(CHATGPT_ALARM, { periodInMinutes: 1 });
  ensureRefreshMonitor().catch(() => {});
}
chrome.runtime.onInstalled.addListener(installPeriodicRefresh);
chrome.runtime.onStartup.addListener(installPeriodicRefresh);
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === CHATGPT_ALARM) requestRefresh("ChatGPT");
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (tabId !== pendingTabId || changeInfo.status !== "complete") return;
  scheduleFallbackClose(tabId, pendingWindowId, pendingProvider);
});
chrome.tabs.onRemoved.addListener(tabId => {
  if (tabId === pendingTabId) {
    pendingTabId = null; pendingWindowId = null; pendingProvider = null;
    drainRefreshQueue(true).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "refresh-request") {
    sendResponse({ ok: requestRefresh(message.provider, true) });
    return;
  }
  if (message && message.type === "periodic-refresh") {
    sendResponse({ ok: requestRefresh(message.provider, false) });
    return;
  }
  if (!message || message.type !== "usage-update") return;
  fetch(LOCAL_RECEIVER, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(message.payload)
  }).then(response => {
    if (response.ok && sender.tab && sender.tab.id === pendingTabId) {
      setTimeout(closePendingWindow, 1000);
    }
    sendResponse({ ok: response.ok });
  }).catch(error => sendResponse({ ok: false, error: String(error) }));
  return true;
});

ensureRefreshMonitor().catch(() => {});
installPeriodicRefresh();
