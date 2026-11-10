// Prefer the same signed-in, read-only usage requests used by the provider
// pages. Visible text remains a fallback for accounts with a different shape.
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

async function fetchJson(url) {
  const response = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

async function fetchClaudeUsage() {
  let organizations;
  try { organizations = await fetchJson("/api/organizations"); }
  catch (_) { return null; }
  const list = Array.isArray(organizations) ? organizations : organizations.organizations || [];
  // Prefer the organization used by the current page, then try the remaining
  // memberships. Some accounts expose both a personal and a team org.
  const pathMatch = location.pathname.match(/organizations\/([0-9a-f-]{20,})/i);
  const pathOrg = pathMatch ? pathMatch[1] : null;
  const chatOrganizations = list.filter(org => Array.isArray(org.capabilities) && org.capabilities.includes("chat"));
  const ids = [...new Set([
    pathOrg,
    ...chatOrganizations.map(org => org.uuid || org.id || org.organization_uuid),
    ...list.map(org => org.uuid || org.id || org.organization_uuid)
  ].filter(Boolean))];
  for (const id of ids) {
    try {
      const payload = UsageParsers.parseClaude(await fetchJson(`/api/organizations/${encodeURIComponent(id)}/usage`));
      if (payload) return payload;
    } catch (_) {}
  }
  return null;
}

let publishing = false;
async function publish() {
  if (publishing) return;
  publishing = true;
  const text = normalizedText();
  try {
    const payload = await fetchClaudeUsage() || extractClaude(text);
    if (!payload) return;
    Object.values(payload.windows).forEach(item => {
      if (item.used === null || item.used === undefined) delete item.used;
      if (!item.reset_label) delete item.reset_label;
    });
    // Chrome can reload or suspend the service worker while a usage page stays open.
    // A failed one-way update must not create a visible extension error.
    try {
      const sent = chrome.runtime.sendMessage({ type: "usage-update", payload });
      if (sent && typeof sent.catch === "function") sent.catch(() => {});
    } catch (_) {}
  } finally {
    publishing = false;
  }
}
let debounce;
new MutationObserver(() => { clearTimeout(debounce); debounce = setTimeout(() => publish(), 800); }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
publish(); setInterval(() => publish(), 30000);
