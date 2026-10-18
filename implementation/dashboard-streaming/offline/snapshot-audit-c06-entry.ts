// ADOPT-C06 regression entry — storage-error visibility.
// Bundled and executed by offline/snapshot-audit-c06.mjs against
// disposable in-memory storage, using the package's own server
// sources (with the C06 fix), the verbatim 0002/0003 DDL, and the
// same disclosed substitutions as the C1 audit line: the lane's
// offline adapter stands in for @hatch/space-sdk (defineAction =
// identity; platform schema validation not run) and global fetch is
// an in-memory stub (no real feed is contacted).
//
// Fault injection is a TEST-ONLY trigger added to the disposable
// database (`c06_fault`: RAISE(ABORT) on insert) and dropped for the
// recovery steps. It never touches a real disk or production storage.
// Verdicts are computed from observations; the receipt is written by
// the driver.
//
// @ts-nocheck — offline harness entry, bundled by snapshot-audit-c06.mjs.
import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import { readFileSync } from "node:fs";
import { Actions } from "../server/src/actions.ts";
import * as schema from "../server/src/schema.ts";

// Synthetic feed frame in the raw /feed/all shape normalize() consumes
// (same construction as the C1 audit entry; no committed fixture file
// is read, so the harness is self-contained inside this tree).
function rawFrame(updatedAt, spot) {
  return {
    status: "ok",
    updated_at: updatedAt,
    quote_as_of: updatedAt,
    market_open: true,
    spot,
    expiry: "2026-10-16",
    gamma: {
      spot,
      net_gex_m: -123.4,
      gamma_flip: 768.5,
      call_wall: 775,
      put_wall: 765,
      max_pain: 770,
      regime: "negative",
      speed_m_per_pt2: 1.5,
      speed_wide_m_per_pt2: 2.5,
      by_strike: [
        { strike: 765, net_gex_m: 0, call_gex_m: 10.5, put_gex_m: -10.5, src: "rtd" },
        { strike: 770, net_gex_m: null, call_gex_m: null, put_gex_m: null, src: null },
      ],
      top_strikes: [],
    },
    positioning: {
      pin_score: 42.5,
      pin_magnet: 770,
      pin_components: { concentration: 0.5, proximity: 0.6, time_elapsed: 0.7 },
      expected_move: { dollars: 8.5, pct: 1.1, remaining_dollars: 3.25 },
      hedge_buckets: [],
      dealer_gamma_notional_m_per_pt: 12.3,
      reversal_watch: { conditions: [], stretched: false },
    },
    flow: {
      pc_volume: 1.05,
      pc_oi: 0.98,
      call_volume: 1000,
      put_volume: 1100,
      elevated_volume_activity: [],
    },
    iv: { atm_call_iv: 0.21, atm_put_iv: 0.22, risk_reversal_25d: null },
    vanna_charm: { total_vanna_k: 3.1, total_charm_k: -2.2 },
    sources: { nasdaq: { as_of: updatedAt, stale: false } },
    n_strikes_rtd_live: 3,
    n_strikes_nasdaq_delayed: 40,
  };
}
const DDL_0002 = readFileSync(
  new URL("../drizzle/0002_snapshots_table.sql", import.meta.url), "utf8",
);
const DDL_0003 = readFileSync(
  new URL("../drizzle/0003_snapshot_instant.sql", import.meta.url), "utf8",
);

const getLive = Actions.getLive.handler;

let feedFrame = null; // null => feed down
globalThis.fetch = async () => {
  if (feedFrame === null) return { ok: false, status: 503, json: async () => ({}) };
  const body = structuredClone(feedFrame);
  return { ok: true, status: 200, json: async () => body };
};

async function applyDdl(client, ddl) {
  for (const stmt of ddl.split("--> statement-breakpoint")) {
    const sql = stmt.trim();
    if (sql) await client.execute(sql);
  }
}
async function createDb() {
  const client = createClient({ url: ":memory:" });
  await applyDdl(client, DDL_0002);
  await applyDdl(client, DDL_0003);
  const db = drizzle(client, { schema });
  return { client, ctx: { db: () => db, user: null, requestId: "c06-audit" } };
}
async function storedRows(client) {
  const r = await client.execute(
    "SELECT id, updated_at, instant_ms, spot FROM snapshots ORDER BY id ASC",
  );
  return r.rows.map((row) => ({
    id: Number(row.id),
    updated_at: String(row.updated_at),
    instant_ms: row.instant_ms === null ? null : Number(row.instant_ms),
    spot: row.spot === null ? null : Number(row.spot),
  }));
}
async function setFault(client, on) {
  await client.execute(
    on
      ? "CREATE TRIGGER c06_fault BEFORE INSERT ON snapshots BEGIN SELECT RAISE(ABORT, 'c06 injected storage failure'); END"
      : "DROP TRIGGER IF EXISTS c06_fault",
  );
}

const BASE = Date.parse("2026-10-16T23:30:00Z");
const iso = (plusSec) => new Date(BASE + plusSec * 1000).toISOString();
const OFF = "2026-10-17T01:30:00+02:00"; // == iso(0) spelled +02:00
function frameAt(updatedAt, spot) {
  return rawFrame(updatedAt, spot);
}
async function live(ctx, frame) {
  feedFrame = frame;
  return await getLive(ctx);
}

const cases = [];
function record(id, expectation, pass, observed) {
  cases.push({ id, expectation, verdict: pass ? "PASS" : "FAIL", observed });
  console.log("C06AUDIT " + id + " " + (pass ? "PASS" : "FAIL") + " — " + expectation);
}

// S01 — non-unique insert failure with NO prior rows: the feed stays
// truthful (ok, live frame present), persistence explicitly reports
// the failure with a safe category, and no saved observation is
// claimed (no row, empty trail).
{
  const { client, ctx } = await createDb();
  await setFault(client, true);
  const resp = await live(ctx, frameAt(iso(0), 500));
  const rows = await storedRows(client);
  record(
    "S01",
    "insert failure, empty storage: ok:true with live frame, persistence failed/storage-unavailable, 0 rows, empty trail",
    resp.ok === true &&
      resp.live !== null &&
      resp.live.spot === 500 &&
      resp.persistence.outcome === "failed" &&
      resp.persistence.reason === "storage-unavailable" &&
      rows.length === 0 &&
      resp.trail.length === 0,
    {
      ok: resp.ok,
      persistence: resp.persistence,
      rows: rows.length,
      trailLength: resp.trail.length,
    },
  );
}

// S02 — failure with an existing last-good trail: stored rows and the
// trail remain intact, the new live frame is still shown, and the
// persistence failure is explicit (the reviewer's C06 witness,
// corrected).
{
  const { client, ctx } = await createDb();
  const first = await live(ctx, frameAt(iso(0), 500));
  await setFault(client, true);
  const failed = await live(ctx, frameAt(iso(60), 501));
  const rows = await storedRows(client);
  record(
    "S02",
    "insert failure with last-good trail: first frame saved; failed response keeps ok:true + new live frame, persistence failed, rows stay 1, trail stays at the first frame",
    first.persistence.outcome === "saved" &&
      failed.ok === true &&
      failed.live !== null &&
      failed.live.spot === 501 &&
      failed.persistence.outcome === "failed" &&
      failed.persistence.reason === "storage-unavailable" &&
      rows.length === 1 &&
      failed.trail.length === 1 &&
      failed.trail[0].updatedAt === iso(0),
    {
      first: first.persistence,
      failed: failed.persistence,
      rows: rows.length,
      trail: failed.trail.map((t) => t.updatedAt),
    },
  );

  // S03 — same-frame recovery: fault cleared, the SAME frame is
  // redelivered and saved exactly once under its original identity;
  // the outcome flips to saved (the UI warning therefore clears on
  // the next response), and an exact replay is a benign already-saved.
  await setFault(client, false);
  const recovered = await live(ctx, frameAt(iso(60), 501));
  const replay = await live(ctx, frameAt(iso(60), 501));
  const rowsAfter = await storedRows(client);
  record(
    "S03",
    "recovery: redelivered frame saves exactly once (rows 2, trail catches up), persistence saved; exact replay is already-saved with no duplicate",
    recovered.persistence.outcome === "saved" &&
      recovered.trail.length === 2 &&
      recovered.trail[1].updatedAt === iso(60) &&
      replay.persistence.outcome === "already-saved" &&
      rowsAfter.length === 2,
    {
      recovered: recovered.persistence,
      replay: replay.persistence,
      rows: rowsAfter.length,
      trail: recovered.trail.map((t) => t.updatedAt),
    },
  );
}

// S04 — benign outcomes never report a failure: throttle and the
// atomic paired-write overlap resolve to throttled / saved +
// already-saved with reason null throughout.
{
  const { client, ctx } = await createDb();
  const first = await live(ctx, frameAt(iso(0), 500));
  const throttled = await live(ctx, frameAt(iso(30), 502));
  const rows = await storedRows(client);
  const pair = await createDb();
  const [p1, p2] = await Promise.all([
    live(pair.ctx, frameAt(iso(0), 500)),
    live(pair.ctx, frameAt(OFF, 999)),
  ]);
  const pairRows = await storedRows(pair.client);
  const pairOutcomes = [p1.persistence.outcome, p2.persistence.outcome].sort();
  record(
    "S04",
    "benign outcomes: +30s frame is throttled (no row, no failure); overlapping equivalent-instant pair yields saved + already-saved, exactly 1 row, no failure anywhere",
    first.persistence.outcome === "saved" &&
      throttled.persistence.outcome === "throttled" &&
      throttled.persistence.reason === null &&
      rows.length === 1 &&
      pairOutcomes.join(",") === "already-saved,saved" &&
      pairRows.length === 1 &&
      p1.persistence.reason === null &&
      p2.persistence.reason === null,
    {
      first: first.persistence,
      throttled: throttled.persistence,
      pair: pairOutcomes,
      pairRows: pairRows.length,
    },
  );
}

// S05 — feed-down responses carry an honest no-attempt: persistence
// is present in the declared shape and never dressed up as saved.
{
  const { ctx } = await createDb();
  const down = await live(ctx, null);
  record(
    "S05",
    "feed down: ok:false and persistence { outcome: no-attempt, reason: null }",
    down.ok === false &&
      down.persistence.outcome === "no-attempt" &&
      down.persistence.reason === null,
    { ok: down.ok, persistence: down.persistence },
  );
}

import { writeFileSync } from "node:fs";
const outDir = process.argv[2];
if (outDir) {
  writeFileSync(
    outDir + "/c06-cases.json",
    JSON.stringify({ cases }, null, 2) + "\n",
  );
}
console.log("C06AUDIT-END");
