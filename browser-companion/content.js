// Reads only visible usage-card text and sends the parsed values to localhost.
function normalizedText() {
  return ((document.body && document.body.innerText) || "").replace(/\s+/g, " ").trim();
}
function percentAfter(text, anchor) {
  const at = text.toLowerCase().indexOf(anchor.toLowerCase());
  if (at < 0) return null;
  const slice = text.slice(at, at + 500);
  const match = slice.match(/(\d+(?:\.\d+)?)%\s*(used|left|remaining)/i);
  if (!match) return null;
  const number = Number(match[1]);
  return /left|remaining/i.test(match[2]) ? 100 - number : number;
}
function resetAfter(text, anchor) {
  const at = text.toLowerCase().indexOf(anchor.toLowerCase());
  if (at < 0) return null;
  const slice = text.slice(at, at + 500);
  const match = slice.match(/Resets?\s+(?:in\s+)?(.+?)(?=\s+\d+(?:\.\d+)?%|\s+(?:Usage limit resets|Last updated|Usage credits|Credits remaining|Auto reload|Usage breakdown|Personal usage)|$)/i);
  return match ? `Resets ${match[1].trim()}` : null;
}
function extractClaude(text) {
  if (!/Plan usage limits|Weekly limits/i.test(text)) return null;
  return { provider: "Claude", windows: {
    "5-hour": { used: percentAfter(text, "Current session"), reset_label: resetAfter(text, "Current session") },
    "Weekly": { used: percentAfter(text, "All models"), reset_label: resetAfter(text, "All models") }
  }};
}
function extractChatGPT(text) {
  const anchor = /Weekly usage limit/i.test(text) ? "Weekly usage limit" : /Weekly limit/i.test(text) ? "Weekly limit" : null;
  if (!anchor) return null;
  return { provider: "ChatGPT", windows: { "Weekly": {
    used: percentAfter(text, anchor), reset_label: resetAfter(text, anchor)
  }}};
}
function publish() {
  const text = normalizedText();
  const payload = location.hostname.includes("claude.ai") ? extractClaude(text) : extractChatGPT(text);
  if (!payload) return;
  Object.values(payload.windows).forEach(item => { if (item.used === null) delete item.used; if (!item.reset_label) delete item.reset_label; });
  // Chrome can reload or suspend the service worker while a usage page stays open.
  // A failed one-way update must not create a visible extension error.
  try {
    const sent = chrome.runtime.sendMessage({ type: "usage-update", payload });
    if (sent && typeof sent.catch === "function") sent.catch(() => {});
  } catch (_) {}
}
let debounce;
new MutationObserver(() => { clearTimeout(debounce); debounce = setTimeout(publish, 800); }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
publish(); setInterval(publish, 30000);
