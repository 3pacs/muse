#!/usr/bin/env node
/**
 * ADOPT-F1 boundary tests — portable, offline, zero-dependency.
 *
 * Extracts the marked ADOPT-F1 pure-helper blocks VERBATIM from the
 * production sources (server/src/actions.ts, client/src/App.tsx) and runs
 * domain assertions against the extracted code — the same functions the
 * app ships, not copies. Requires Node >= 22.18 (native type stripping)
 * or any runtime that can import an erasable-syntax .ts module.
 *
 * Run:  node tests/boundaries.test.mjs        (exit 1 on any failure)
 */
import { readFileSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");

let pass = 0;
let fail = 0;
function check(name, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log("PASS " + name);
  } else {
    fail += 1;
    console.log("FAIL " + name + (detail ? " — " + detail : ""));
  }
}

function extractBlock(file, label) {
  const text = readFileSync(join(root, file), "utf8");
  const start = text.indexOf("// === ADOPT-F1 PURE HELPERS");
  const end = text.indexOf("// === END ADOPT-F1 PURE HELPERS ===");
  if (start < 0 || end < 0 || end <= start) {
    throw new Error(label + ": ADOPT-F1 helper block markers not found in " + file);
  }
  return text.slice(start, end);
}

const dir = mkdtempSync(join(tmpdir(), "adopt-f1-"));

const serverBlock = extractBlock("server/src/actions.ts", "server");
for (const fn of ["num", "mapStrikes", "strikeCoverage", "parseAwareInstant", "updateClockAcceptable"]) {
  check("server block exposes " + fn, serverBlock.includes("function " + fn));
}
writeFileSync(
  join(dir, "server-helpers.ts"),
  serverBlock +
    "\nexport { num, str, obj, mapStrikes, strikeCoverage, parseAwareInstant, updateClockAcceptable };\n",
);
const S = await import(pathToFileURL(join(dir, "server-helpers.ts")).href);

const clientBlock = extractBlock("client/src/App.tsx", "client");
for (const fn of ["parseAwareMs", "feedAgeMs", "selectConnStatus", "clusterState"]) {
  check("client block exposes " + fn, clientBlock.includes("function " + fn));
}
writeFileSync(
  join(dir, "client-helpers.ts"),
  clientBlock +
    "\nexport { parseAwareMs, feedAgeMs, selectConnStatus, clusterState };\n",
);
const C = await import(pathToFileURL(join(dir, "client-helpers.ts")).href);

// ---------------------------------------------------------------- GEX ----
const g = (rows) => S.mapStrikes(rows);
let r = g([{ strike: 770, net_gex_m: 0, call_gex_m: 0, put_gex_m: 0, src: "live" }]);
check("gex: genuine zero preserved", r.length === 1 && r[0].netGexM === 0 && r[0].callGexM === 0 && r[0].putGexM === 0);
r = g([{ strike: 770 }]);
check("gex: missing keys stay null (unavailable)", r.length === 1 && r[0].netGexM === null && r[0].callGexM === null && r[0].putGexM === null);
r = g([{ strike: 770, net_gex_m: null, call_gex_m: null, put_gex_m: null }]);
check("gex: explicit nulls stay null", r[0].netGexM === null && r[0].callGexM === null && r[0].putGexM === null);
r = g([{ strike: 770, net_gex_m: "abc", call_gex_m: {}, put_gex_m: NaN }]);
check("gex: non-numeric values stay null", r[0].netGexM === null && r[0].callGexM === null && r[0].putGexM === null);
r = g([{ strike: 770, net_gex_m: "12.5" }]);
check("gex: numeric string still parses (num contract)", r[0].netGexM === 12.5);
r = g([{ net_gex_m: 5 }, { strike: "771", net_gex_m: -3 }]);
check("gex: strike-less row excluded, string strike parses", r.length === 1 && r[0].strike === 771 && r[0].netGexM === -3);
const cov = S.strikeCoverage(g([
  { strike: 1, net_gex_m: 0 },
  { strike: 2 },
  { strike: 3, net_gex_m: 5 },
  { strike: 4, net_gex_m: null },
]));
check("gex: coverage counts zero as known", cov.total === 4 && cov.gexKnown === 2 && cov.gexMissing === 2, JSON.stringify(cov));

// ------------------------------------------------------------- clocks ------
const NOW = Date.parse("2026-01-05T15:00:00Z");
check("clock: aware Z accepted", S.updateClockAcceptable("2026-01-05T14:59:00Z", NOW) === true);
check("clock: aware +00:00 accepted", S.updateClockAcceptable("2026-01-05T14:59:00+00:00", NOW) === true);
check("clock: aware -05:00 accepted", S.updateClockAcceptable("2026-01-05T09:59:00-05:00", NOW) === true);
check("clock: timezone-less rejected", S.updateClockAcceptable("2026-01-05T14:59:00", NOW) === false);
check("clock: garbage rejected", S.updateClockAcceptable("not-a-clock", NOW) === false);
check("clock: empty rejected", S.updateClockAcceptable("", NOW) === false);
check("clock: null rejected", S.updateClockAcceptable(null, NOW) === false);
check("clock: numeric rejected", S.updateClockAcceptable(1767650340000, NOW) === false);
check("clock: one day in the future rejected", S.updateClockAcceptable("2026-01-06T15:00:00Z", NOW) === false);
check("clock: +60s inside explicit skew allowance", S.updateClockAcceptable("2026-01-05T15:01:00Z", NOW) === true);
check("clock: parseAwareInstant exact ms", S.parseAwareInstant("2026-01-05T14:59:00Z") === Date.parse("2026-01-05T14:59:00Z"));
check("clock: parseAwareInstant naive -> null", S.parseAwareInstant("2026-01-05 14:59:00") === null);

// --------------------------------------------------------- client age ------
check("age: fresh aware frame", C.feedAgeMs("2026-01-05T14:59:30Z", NOW) === 30000);
check("age: timezone-less -> null", C.feedAgeMs("2026-01-05T14:59:30", NOW) === null);
check("age: garbage -> null", C.feedAgeMs("garbage", NOW) === null);
check("age: future +1 day -> null", C.feedAgeMs("2026-01-06T15:00:00Z", NOW) === null);
check("age: future +60s clamps to 0", C.feedAgeMs("2026-01-05T15:01:00Z", NOW) === 0);
check("age: old frame exact", C.feedAgeMs("2026-01-05T14:50:00Z", NOW) === 600000);

// ------------------------------------------------------------ status -------
const base = {
  paused: false, hasData: true, isError: false, showingStale: false,
  dataOk: true, marketOpen: true, ageMs: 5000,
};
check("status: fresh + valid clock -> live", C.selectConnStatus(base) === "live");
check("status: age 0 -> live", C.selectConnStatus({ ...base, ageMs: 0 }) === "live");
check("status: old age -> stale", C.selectConnStatus({ ...base, ageMs: 121000 }) === "stale");
check("status: unverifiable clock -> stale, never live", C.selectConnStatus({ ...base, ageMs: null }) === "stale");
check("status: paused wins", C.selectConnStatus({ ...base, paused: true }) === "paused");
check("status: no data -> down", C.selectConnStatus({ ...base, hasData: false }) === "down");
check("status: query error -> down", C.selectConnStatus({ ...base, isError: true }) === "down");
check("status: showing stale snapshot -> down", C.selectConnStatus({ ...base, showingStale: true }) === "down");
check("status: action not ok -> down", C.selectConnStatus({ ...base, dataOk: false }) === "down");
check("status: market closed -> closed", C.selectConnStatus({ ...base, marketOpen: false }) === "closed");
check(
  "status: end-to-end future clock never live",
  C.selectConnStatus({ ...base, ageMs: C.feedAgeMs("2026-01-06T15:00:00Z", NOW) }) === "stale",
);
check(
  "status: end-to-end naive clock never live",
  C.selectConnStatus({ ...base, ageMs: C.feedAgeMs("2026-01-05T14:59:30", NOW) }) === "stale",
);

// ----------------------------------------------------------- clustering ----
let cs = C.clusterState(true, 3);
check("cluster: true -> clustering with count", cs.kind === "clustering" && cs.text.includes("3 in last hour"), cs.text);
cs = C.clusterState(true, null);
check("cluster: true + unknown count -> clustering", cs.kind === "clustering" && cs.text.includes("count unknown"), cs.text);
cs = C.clusterState(false, 1);
check("cluster: explicit false -> isolated", cs.kind === "isolated" && cs.text === "isolated");
cs = C.clusterState(null, null);
check("cluster: legacy null -> unknown, NOT isolated", cs.kind === "unknown" && cs.text !== "isolated", cs.text);
cs = C.clusterState(undefined, undefined);
check("cluster: missing tag -> unknown", cs.kind === "unknown");

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
