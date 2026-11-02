// Pure normalization helpers shared by the browser companion and its tests.
(function (root) {
  "use strict";

  function number(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function firstDefined() {
    for (let i = 0; i < arguments.length; i += 1) {
      if (arguments[i] !== null && arguments[i] !== undefined) return arguments[i];
    }
    return undefined;
  }

  function resetLabel(value) {
    if (value === null || value === undefined || value === "") return null;
    let date;
    if (typeof value === "number") date = new Date(value * 1000);
    else if (/^\d+(?:\.\d+)?$/.test(String(value))) date = new Date(Number(value) * 1000);
    else date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return `Resets ${date.toLocaleString([], {
      weekday: "short", hour: "numeric", minute: "2-digit"
    })}`;
  }

  function normalizedWindow(window) {
    if (!window || typeof window !== "object") return null;
    const used = number(firstDefined(window.used_percent, window.usedPercent, window.utilization, window.used_percentage));
    const reset = firstDefined(window.reset_at, window.resets_at, window.resetsAt);
    if (used === null && reset === undefined) return null;
    return { used, reset_label: resetLabel(reset) };
  }

  function parseClaude(data) {
    if (!data || typeof data !== "object") return null;
    const session = normalizedWindow(firstDefined(data.five_hour, data.fiveHour));
    const weekly = normalizedWindow(firstDefined(data.seven_day, data.sevenDay, data.weekly));
    if (!session && !weekly) return null;
    return { provider: "Claude", windows: {
      "5-hour": session || { unavailable: true },
      "Weekly": weekly || { unavailable: true }
    } };
  }

  const api = { parseClaude, resetLabel };
  root.UsageParsers = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
