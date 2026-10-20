// ADOPT-C07 regression entry — bounded last-good fallback recovery.
//
// Bundled and executed by offline/snapshot-audit-c07.mjs against
// disposable in-memory storage, using the package's own server
// sources (with the C07 fix), the verbatim 0002/0003 DDL, and the
// same disclosed substitutions as the C1/C06 audit lines: the lane's
// offline adapter stands in for @hatch/space-sdk (defineAction =
// identity; platform schema validation not run) and global fetch is
// an in-memory stub (no real feed is contacted).
//
// Cases seed stored rows DIRECTLY (SQL inserts into the disposable
// database, payload_json bytes exactly as written) wherever the
// case needs a stored state the live path would never produce
// (corrupt JSON, payload/metadata identity mismatch, >240 rows).
// Those inserts are test setup against disposable storage only; the
// code under test never rewrites or deletes them, and case T02
// asserts both stored rows are byte-unchanged after the fallback.
// Verdicts are computed from observations; the receipt is written
// by the driver.
//
// @ts-nocheck — offline harness entry, bundled by snapshot-audit-c07.mjs.
import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import { readFileSync } from "node:fs";
import { Actions } from "../server/src/actions.ts";
import * as schema from "../server/src/schema.ts";

// Synthetic feed frame in the raw /feed/all shape normalize() consumes
// (same construction as the C1/C06 audit entries; no committed fixture
// file is read, so the harness is self-contained inside this tree).
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
  return { client, ctx: { db: () => db, user: null, requestId: "c07-audit" } };
}
// Direct seed of a stored row with EXACT payload bytes (test setup
// only — see header). Scalar columns other than spot are null; the
// fallback path reads updated_at / instant_ms / payload_json.
async function seedRow(client, updatedAt, instantMs, payloadJson, spot) {
  await client.execute({
    sql: "INSERT INTO snapshots (updated_at, instant_ms, spot, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
    args: [updatedAt, instantMs, spot, payloadJson, 1700000000000],
  });
}
async function storedRows(client) {
  const r = await client.execute(
    "SELECT id, updated_at, instant_ms, spot, payload_json FROM snapshots ORDER BY id ASC",
  );
  return r.rows.map((row) => ({
    id: Number(row.id),
    updated_at: String(row.updated_at),
    instant_ms: row.instant_ms === null ? null : Number(row.instant_ms),
    spot: row.spot === null ? null : Number(row.spot),
    payload_json: String(row.payload_json),
  }));
}
async function live(ctx, frame) {
  feedFrame = frame;
  return await getLive(ctx);
}
const down = async (ctx) => live(ctx, null);

const BASE = Date.parse("2026-10-16T23:30:00Z");
const iso = (plusSec) => new Date(BASE + plusSec * 1000).toISOString();

const cases = [];
function record(id, expectation, pass, observed) {
  cases.push({ id, expectation, verdict: pass ? "PASS" : "FAIL", observed });
  console.log("C07AUDIT " + id + " " + (pass ? "PASS" : "FAIL") + " — " + expectation);
}

// T01 (acceptance a) — newest usable: selected unchanged, coherent
// pair, reason "current".
{
  const { client, ctx } = await createDb();
  const saved = await live(ctx, rawFrame(iso(0), 500));
  const resp = await down(ctx);
  record(
    "T01",
    "newest usable: feed-down returns it unchanged (spot 500), staleSnapshotAt is its own timestamp, reason current",
    saved.persistence.outcome === "saved" &&
      resp.ok === false &&
      resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshot.updatedAt === iso(0) &&
      resp.staleSnapshotAt === iso(0) &&
      resp.staleSnapshotReason === "current",
    {
      ok: resp.ok,
      staleSpot: resp.staleSnapshot?.spot ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T02 (acceptance b) — newest corrupt JSON, older usable: the older
// payload is returned with ITS timestamp, reason "earlier-usable",
// and BOTH stored rows are byte-unchanged afterwards.
{
  const { client, ctx } = await createDb();
  await seedRow(client, iso(0), BASE, JSON.stringify(rawFrame(iso(0), 500)), 500);
  await seedRow(client, iso(120), BASE + 120000, "{corrupt payload bytes", 501);
  const before = await storedRows(client);
  const resp = await down(ctx);
  const after = await storedRows(client);
  record(
    "T02",
    "newest corrupt JSON + older usable: older payload with its own timestamp, reason earlier-usable, both stored rows byte-unchanged",
    resp.ok === false &&
      resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshotAt === iso(0) &&
      resp.staleSnapshotReason === "earlier-usable" &&
      JSON.stringify(before) === JSON.stringify(after),
    {
      staleSpot: resp.staleSnapshot?.spot ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
      rowsUnchanged: JSON.stringify(before) === JSON.stringify(after),
    },
  );
}

// T03 (acceptance c) — newest parses but fails F1 admission
// (payload updated_at is not a timezone-aware instant, so
// normalize() returns null): skipped; next usable selected.
{
  const { client, ctx } = await createDb();
  await seedRow(client, iso(0), BASE, JSON.stringify(rawFrame(iso(0), 500)), 500);
  const inadmissible = rawFrame("2026-10-16 23:32:00", 501); // naive clock
  await seedRow(client, iso(120), BASE + 120000, JSON.stringify(inadmissible), 501);
  const resp = await down(ctx);
  record(
    "T03",
    "newest parses but fails admission (naive payload clock): skipped, older usable selected, reason earlier-usable",
    resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshotAt === iso(0) &&
      resp.staleSnapshotReason === "earlier-usable",
    {
      staleSpot: resp.staleSnapshot?.spot ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T04 (acceptance d) — payload identity mismatch: the newest row's
// payload clock names a DIFFERENT instant than the row's keyed
// instant. The payload normalizes on its own, but it must not
// silently become this row's last-good frame: skipped.
{
  const { client, ctx } = await createDb();
  await seedRow(client, iso(0), BASE, JSON.stringify(rawFrame(iso(0), 500)), 500);
  // Row keyed at iso(120); its payload clock says iso(0), spot 501.
  await seedRow(client, iso(120), BASE + 120000, JSON.stringify(rawFrame(iso(0), 501)), 501);
  const resp = await down(ctx);
  record(
    "T04",
    "payload identity mismatch (payload clock != row instant): skipped, older coherent usable selected, reason earlier-usable",
    resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshotAt === iso(0) &&
      resp.staleSnapshotReason === "earlier-usable",
    {
      staleSpot: resp.staleSnapshot?.spot ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T05 (acceptance e) — equivalent aware spelling: the row's stored
// timestamp spells the instant with +02:00 while the payload spells
// it with Z (.000Z). Same canonical instant: usable, reason
// "current", and staleSnapshotAt preserves the ROW's raw spelling.
{
  const { client, ctx } = await createDb();
  const rowSpelling = "2026-10-17T01:30:00+02:00"; // == BASE
  await seedRow(client, rowSpelling, BASE, JSON.stringify(rawFrame(iso(0), 500)), 500);
  const resp = await down(ctx);
  record(
    "T05",
    "equivalent aware spelling (+02:00 row, Z payload, same instant): usable, reason current, staleSnapshotAt is the row's raw +02:00 spelling, payload preserved",
    resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshot.updatedAt === iso(0) &&
      resp.staleSnapshotAt === rowSpelling &&
      resp.staleSnapshotReason === "current",
    {
      staleSpot: resp.staleSnapshot?.spot ?? null,
      payloadUpdatedAt: resp.staleSnapshot?.updatedAt ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T06 (acceptance f) — empty storage: both fallback fields null,
// reason "empty-storage".
{
  const { ctx } = await createDb();
  const resp = await down(ctx);
  record(
    "T06",
    "empty storage: staleSnapshot null, staleSnapshotAt null, reason empty-storage",
    resp.ok === false &&
      resp.staleSnapshot === null &&
      resp.staleSnapshotAt === null &&
      resp.staleSnapshotReason === "empty-storage" &&
      resp.trail.length === 0,
    {
      staleSnapshot: resp.staleSnapshot,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T07 (acceptance g) — candidates exist, all unusable, fewer than
// the bound: both null, reason "no-usable-candidate".
{
  const { client, ctx } = await createDb();
  for (let i = 0; i < 3; i++) {
    await seedRow(client, iso(i * 60), BASE + i * 60000, "{broken " + i, 500 + i);
  }
  const resp = await down(ctx);
  record(
    "T07",
    "3 candidates, all corrupt (< bound): both fallback fields null, reason no-usable-candidate",
    resp.staleSnapshot === null &&
      resp.staleSnapshotAt === null &&
      resp.staleSnapshotReason === "no-usable-candidate",
    {
      staleSnapshot: resp.staleSnapshot,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T08 (acceptance h) — bound exhausted: 245 keyed rows; the first
// 240 in scan order (newest) are all corrupt, and a usable row
// exists ONLY beyond the bound. The fallback must stay null with
// reason "window-exhausted" — returning the beyond-bound row would
// prove the scan unbounded, claiming "no usable fallback anywhere"
// would overclaim; the window wording is the truthful one.
{
  const { client, ctx } = await createDb();
  await seedRow(client, iso(0), BASE, JSON.stringify(rawFrame(iso(0), 500)), 500);
  for (let i = 1; i <= 244; i++) {
    await seedRow(client, iso(i * 60), BASE + i * 60000, "{broken " + i, 500);
  }
  const rows = await storedRows(client);
  const resp = await down(ctx);
  record(
    "T08",
    "245 rows, newest 240 corrupt, usable row beyond the bound: both fallback fields null, reason window-exhausted (scan stayed bounded — the beyond-bound usable row was NOT returned), all 245 rows still stored",
    rows.length === 245 &&
      resp.staleSnapshot === null &&
      resp.staleSnapshotAt === null &&
      resp.staleSnapshotReason === "window-exhausted",
    {
      storedRows: rows.length,
      staleSnapshot: resp.staleSnapshot,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T09 (acceptance i) — the reviewer's C07 witness, exactly: frames
// 23:30 spot 500 and 23:31 spot 501 stored; the 23:31 payload is
// corrupted in storage; feed down. Previously this returned a null
// payload beside staleSnapshotAt 23:31 with no reason. Now it must
// return the 23:30 frame with staleSnapshotAt 23:30 and reason
// "earlier-usable", ok:false.
{
  const { client, ctx } = await createDb();
  await seedRow(client, "2026-10-16T23:30:00.000Z", BASE, JSON.stringify(rawFrame("2026-10-16T23:30:00.000Z", 500)), 500);
  await seedRow(client, "2026-10-16T23:31:00.000Z", BASE + 60000, "{corrupted 23:31 payload", 501);
  const resp = await down(ctx);
  record(
    "T09",
    "reviewer C07 witness (23:30 spot 500 / 23:31 spot 501, 23:31 payload corrupt, feed down): returns the 23:30 frame, staleSnapshotAt 23:30, reason earlier-usable, ok:false",
    resp.ok === false &&
      resp.staleSnapshot !== null &&
      resp.staleSnapshot.spot === 500 &&
      resp.staleSnapshotAt === "2026-10-16T23:30:00.000Z" &&
      resp.staleSnapshotReason === "earlier-usable",
    {
      ok: resp.ok,
      staleSpot: resp.staleSnapshot?.spot ?? null,
      staleSnapshotAt: resp.staleSnapshotAt,
      reason: resp.staleSnapshotReason,
    },
  );
}

// T10 — live responses never carry a fallback claim: on ok:true the
// reason and both fallback fields are null (feedError stays about
// the feed only, persistence untouched).
{
  const { ctx } = await createDb();
  const resp = await live(ctx, rawFrame(iso(0), 500));
  record(
    "T10",
    "live response: ok:true, staleSnapshot/staleSnapshotAt/staleSnapshotReason all null, persistence saved",
    resp.ok === true &&
      resp.live !== null &&
      resp.staleSnapshot === null &&
      resp.staleSnapshotAt === null &&
      resp.staleSnapshotReason === null &&
      resp.persistence.outcome === "saved",
    {
      ok: resp.ok,
      reason: resp.staleSnapshotReason,
      persistence: resp.persistence,
    },
  );
}

// T11 — view-state binding (source-level, same pattern as C06 S06):
// the App renders the earlier-usable note only beside the stale
// fallback, and the C06 warning text is untouched.
{
  const appSource = readFileSync(
    new URL("../client/src/App.tsx", import.meta.url),
    "utf8",
  );
  const noteBound =
    appSource.includes('staleSnapshotReason === "earlier-usable"') &&
    appSource.includes("Showing an earlier usable saved frame.");
  const c06Intact =
    appSource.includes("Snapshot saving problem") &&
    appSource.includes("latest saving step");
  record(
    "T11",
    "App binding: earlier-usable note is rendered from staleSnapshotReason beside the stale banner; C06 warning text intact",
    noteBound && c06Intact,
    { noteBound, c06Intact },
  );
}

import { writeFileSync } from "node:fs";
const outDir = process.argv[2];
if (outDir) {
  writeFileSync(
    outDir + "/c07-cases.json",
    JSON.stringify({ cases }, null, 2) + "\n",
  );
}
console.log("C07AUDIT-END");
