const assert = require("assert").strict;
const { parseClaude } = require("./usage-parsers.js");

const claude = parseClaude({
  five_hour: { utilization: 22.5, resets_at: "2026-11-02T20:00:00Z" },
  seven_day: { utilization: 68, resets_at: "2026-11-07T12:00:00Z" }
});
assert.equal(claude.windows["5-hour"].used, 22.5);
assert.equal(claude.windows.Weekly.used, 68);

const resetOnly = parseClaude({ five_hour: {
  utilization: null, resets_at: "2026-11-02T20:00:00Z"
} });
assert.equal(resetOnly.windows["5-hour"].used, null);

console.log("Claude usage parser tests passed");
