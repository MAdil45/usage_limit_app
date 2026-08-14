// Background-only Claude refresh. The tab is inactive, parsed by content.js,
// and closed shortly after its load completes. Chrome limits alarms to 1 min.
const LOCAL_RECEIVER = "http://127.0.0.1:8765/usage";
const CLAUDE_USAGE_URL = "https://claude.ai/settings/usage";
const ALARM_NAME = "claude-usage-refresh";
let pendingTabId = null;
let pendingWindowId = null;

async function widgetIsRunning() {
  try {
    const response = await fetch("http://127.0.0.1:8765/status", { cache: "no-store" });
    return response.ok;
  } catch (_) {
    return false;
  }
}

async function refreshClaude() {
  if (pendingTabId !== null) return;
  // Do not contact Claude unless the desktop widget is actually open.
  if (!(await widgetIsRunning())) return;
  // A separate minimized window keeps the refresh out of the user's tab strip.
  const backgroundWindow = await chrome.windows.create({ url: CLAUDE_USAGE_URL, state: "minimized", focused: false, type: "popup" });
  pendingWindowId = backgroundWindow.id;
  pendingTabId = backgroundWindow.tabs[0].id;
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: 1 });
  refreshClaude();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: 1 });
  refreshClaude();
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === ALARM_NAME) refreshClaude(); });

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (tabId !== pendingTabId || changeInfo.status !== "complete") return;
  setTimeout(async () => {
    try { await chrome.windows.remove(pendingWindowId); } catch (_) {}
    pendingTabId = null; pendingWindowId = null;
  }, 7000);
});
chrome.tabs.onRemoved.addListener(tabId => { if (tabId === pendingTabId) { pendingTabId = null; pendingWindowId = null; } });

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "usage-update") return;
  fetch(LOCAL_RECEIVER, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(message.payload)
  }).then(response => sendResponse({ ok: response.ok }))
    .catch(error => sendResponse({ ok: false, error: String(error) }));
  return true;
});
