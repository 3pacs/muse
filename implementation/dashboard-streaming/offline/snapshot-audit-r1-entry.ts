// ADOPT-C1-R1 regression entry — chronological snapshot identity.
// Bundled and executed by offline/snapshot-audit-r1.mjs against
// disposable in-memory storage, using the package's own server sources
// (with the C1-R1 fix), the verbatim 0002 DDL plus the new 0003
// migration, and the same disclosed substitutions as the C1 audit:
// the lane's offline adapter stands in for @hatch/space-sdk
// (defineAction = identity; platform schema validation not run) and
// global fetch is an in-memory stub (no real feed is contacted).
// Verdicts are computed from observations; the receipt is written by
// the driver. C05/C06/C07 are deferred by the brief and NOT re-tested
// here beyond the controls they share with the R1 acceptance rows.
//
// @ts-nocheck — offline harness entry, bundled by snapshot-audit-r1.mjs.
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
  return { client, ctx: { db: () => db, user: null, requestId: "r1-audit" } };
}
async function createLegacyDb() {
  const client = createClient({ url: ":memory:" });
  await applyDdl(client, DDL_0002); // pre-R1 schema: no instant_ms column
  const db = drizzle(client, { schema });
  return { client, ctx: { db: () => db, user: null, requestId: "r1-legacy" } };
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
  return getLive(ctx);
}
function frameAt(updatedAt, spot) {
  return rawFrame(updatedAt, spot ?? 500);
}
const BASE = Date.parse("2026-10-16T23:30:00Z");
const iso = (sec) => new Date(BASE + sec * 1000).toISOString();
const OFF = "2026-10-17T01:30:00+02:00"; // same instant as iso(0)

const cases = [];
function record(id, expectation, pass, observed) {
  cases.push({ id, expectation, verdict: pass ? "PASS" : "FAIL", observed });
}

// R01 — equivalent-instant interleave (brief acceptance row 1; the C03
// counterexample sequence): 2 distinct instants, not 3 rows.
{
  const { client, ctx } = await createDb();
  await live(ctx, frameAt(iso(0), 700.1));
  await live(ctx, frameAt(OFF, 700.1));
  await live(ctx, frameAt(iso(60), 700.2));
  await live(ctx, frameAt(OFF, 700.1));
  const rows = await storedRows(client);
  const down = await live(ctx, null);
  record(
    "R01",
    "equivalent spellings dedupe by instant even after a newer frame; 2 rows; fallback is the newer frame",
    rows.length === 2 &&
      rows[0].updated_at === iso(0) &&
      rows[1].updated_at === iso(60) &&
      rows.every((r) => r.instant_ms === Date.parse(r.updated_at)) &&
      down.staleSnapshotAt === iso(60) &&
      down.staleSnapshot.spot === 700.2 &&
      JSON.stringify(down.trail.map((t) => t.updatedAt)) ===
        JSON.stringify([iso(0), iso(60)]),
    {
      rowCount: rows.length,
      storedSpellings: rows.map((r) => r.updated_at),
      staleSnapshotAt: down.staleSnapshotAt,
      staleSpot: down.staleSnapshot?.spot ?? null,
    },
  );
}

// R02 — mixed offsets crossing a UTC date boundary, scrambled arrival:
// trail/latest/fallback follow parsed instants; stored spellings kept.
{
  const { client, ctx } = await createDb();
  const A = "2026-10-16T18:58:00-05:00"; // 2026-10-16T23:58:00Z
  const B = "2026-10-17T02:00:30+02:00"; // 2026-10-17T00:00:30Z
  const C = "2026-10-17T00:02:00Z";
  await live(ctx, frameAt(B, 800.2));
  await live(ctx, frameAt(A, 800.1)); // late arrival, older instant
  await live(ctx, frameAt(C, 800.3));
  const rows = await storedRows(client);
  const down = await live(ctx, null);
  record(
    "R02",
    "order follows parsed instants across spellings/dates; original spellings remain stored",
    rows.length === 3 &&
      JSON.stringify(down.trail.map((t) => t.updatedAt)) ===
        JSON.stringify([A, B, C]) &&
      down.staleSnapshotAt === C &&
      rows.find((r) => r.updated_at === A)?.instant_ms === Date.parse(A),
    {
      trail: down.trail.map((t) => t.updatedAt),
      staleSnapshotAt: down.staleSnapshotAt,
    },
  );
}

// R03 — same-instant differing payload: deterministic first-stored-wins,
// no hybrid, no overwrite (storage policy; C05 presentation deferred).
{
  const { client, ctx } = await createDb();
  await live(ctx, frameAt(iso(0), 500));
  await live(ctx, frameAt(OFF, 999));
  const rows = await storedRows(client);
  const down = await live(ctx, null);
  await live(ctx, frameAt(iso(120), 501));
  const rows2 = await storedRows(client);
  record(
    "R03",
    "one row per instant; first stored payload wins in any spelling; no hybrid",
    rows.length === 1 &&
      rows[0].spot === 500 &&
      JSON.parse(rows[0].payload_json).spot === 500 &&
      down.staleSnapshot.spot === 500 &&
      rows2.length === 2,
    {
      rowCountAfterConflict: rows.length,
      storedSpot: rows[0]?.spot ?? null,
      fallbackSpot: down.staleSnapshot?.spot ?? null,
      rowCountAfterNewer: rows2.length,
    },
  );
}

// R04 — legacy rows under the additive 0003 migration (disposable):
// (a) migration deletes/merges/rewrites nothing and backfills instants;
//     post-migration deliveries dedupe against legacy spellings.
// (b) same-instant legacy ties resolve deterministically (highest id).
{
  const legacy = await createLegacyDb();
  const seed = async (updatedAt, spot) => {
    const payload = JSON.stringify(frameAt(updatedAt, spot));
    await legacy.client.execute({
      sql: "INSERT INTO snapshots (updated_at, spot, payload_json, created_at) VALUES (?, ?, ?, ?)",
      args: [updatedAt, spot, payload, 1792000000000],
    });
  };
  await seed("2026-10-16T22:30:00Z", 499); // older instant Y
  await seed(OFF, 500); // instant X, offset spelling (lower id)
  await seed(iso(0), 505); // instant X, Z spelling (higher id)
  const before = await storedRows(legacy.client).catch(() => null);
  const rawBefore = await legacy.client.execute(
    "SELECT id, updated_at, payload_json FROM snapshots ORDER BY id",
  );
  await applyDdl(legacy.client, DDL_0003);
  const after = await storedRows(legacy.client);
  const payloadsIntact =
    rawBefore.rows.every(
      (r, i) => String(r.payload_json) === after[i].payload_json,
    ) &&
    rawBefore.rows.every((r, i) => String(r.updated_at) === after[i].updated_at);
  await live(legacy.ctx, frameAt(iso(0), 777)); // X again, Z spelling
  const afterReplay = await storedRows(legacy.client);
  await live(legacy.ctx, frameAt(iso(60), 501));
  const final = await storedRows(legacy.client);
  record(
    "R04a",
    "0003 is additive: rows/payloads/spellings untouched, instants backfilled; legacy instant dedupes new deliveries",
    after.length === 3 &&
      payloadsIntact &&
      after[1].instant_ms === BASE &&
      after[2].instant_ms === BASE &&
      after[0].instant_ms === BASE - 3600_000 &&
      afterReplay.length === 3 &&
      final.length === 4,
    {
      rowsAfterMigration: after.length,
      backfilled: after.map((r) => r.instant_ms),
      rowsAfterLegacyReplay: afterReplay.length,
      rowsAfterNewFrame: final.length,
      legacySeedBefore: before === null ? "n/a (no instant_ms column pre-migration)" : before,
    },
  );

  const legacy2 = await createLegacyDb();
  const seed2 = async (updatedAt, spot) => {
    await legacy2.client.execute({
      sql: "INSERT INTO snapshots (updated_at, spot, payload_json, created_at) VALUES (?, ?, ?, ?)",
      args: [updatedAt, spot, JSON.stringify(frameAt(updatedAt, spot)), 1792000000000],
    });
  };
  await seed2(OFF, 500);
  await seed2(iso(0), 505);
  await applyDdl(legacy2.client, DDL_0003);
  const down = await live(legacy2.ctx, null);
  record(
    "R04b",
    "same-instant legacy tie resolves deterministically to the highest id",
    down.staleSnapshotAt === iso(0) && down.staleSnapshot.spot === 505,
    { staleSnapshotAt: down.staleSnapshotAt, staleSpot: down.staleSnapshot?.spot ?? null },
  );
}

// R05/R06 — retention exactness in both arrival orders (brief rows 4-5).
const T0 = Date.parse("2026-10-16T00:00:00Z");
const ts = (i) => new Date(T0 + i * 46_000).toISOString();
let ascendingInstants = null;
{
  const { client, ctx } = await createDb();
  for (let i = 0; i <= 1500; i++) await live(ctx, frameAt(ts(i), 500));
  const rows = await storedRows(client);
  ascendingInstants = rows.map((r) => r.instant_ms).sort((a, b) => a - b);
  const down = await live(ctx, null);
  record(
    "R05",
    "ascending 1501 frames retain exactly the newest 1500 instants; trail 240; fallback newest",
    rows.length === 1500 &&
      rows[0].instant_ms === T0 + 46_000 &&
      rows[rows.length - 1].instant_ms === T0 + 1500 * 46_000 &&
      down.trail.length === 240 &&
      down.staleSnapshotAt === ts(1500),
    {
      retained: rows.length,
      minInstant: new Date(rows[0].instant_ms).toISOString(),
      maxInstant: new Date(rows[rows.length - 1].instant_ms).toISOString(),
      staleSnapshotAt: down.staleSnapshotAt,
    },
  );
}
{
  const { client, ctx } = await createDb();
  for (let i = 1500; i >= 0; i--) await live(ctx, frameAt(ts(i), 500));
  const rows = await storedRows(client);
  const instants = rows.map((r) => r.instant_ms).sort((a, b) => a - b);
  const down = await live(ctx, null);
  record(
    "R06",
    "newest-first 1501 frames retain the SAME newest-1500 instant set as ascending; fallback is the newest input instant",
    rows.length === 1500 &&
      JSON.stringify(instants) === JSON.stringify(ascendingInstants) &&
      down.staleSnapshotAt === ts(1500),
    {
      retained: rows.length,
      setMatchesAscending: JSON.stringify(instants) === JSON.stringify(ascendingInstants),
      newestInput: ts(1500),
      staleSnapshotAt: down.staleSnapshotAt,
    },
  );
}

// R07 — older arrival at retention capacity (brief row 6).
{
  const { client, ctx } = await createDb();
  for (let i = 0; i < 1500; i++) await live(ctx, frameAt(ts(i), 500));
  await live(ctx, frameAt(ts(-1), 500)); // older than every retained row
  const rows = await storedRows(client);
  const down = await live(ctx, null);
  record(
    "R07",
    "older arrival at capacity evicts nothing newer, does not survive pruning itself, fallback unregressed",
    rows.length === 1500 &&
      rows[0].instant_ms === T0 &&
      !rows.some((r) => r.instant_ms === T0 - 46_000) &&
      down.staleSnapshotAt === ts(1499),
    {
      retained: rows.length,
      minInstant: new Date(rows[0].instant_ms).toISOString(),
      staleSnapshotAt: down.staleSnapshotAt,
    },
  );
}

// R08 — controls preserved (brief row 7): exact replay, 45s gap,
// genuine zero vs null, honest empty fallback.
{
  const a = await createDb();
  const f = frameAt(iso(0), 500);
  await live(a.ctx, f);
  await live(a.ctx, f);
  await live(a.ctx, f);
  const replayRows = (await storedRows(a.client)).length;

  const b = await createDb();
  const counts = [];
  for (const s of [0, 44, 45, 91]) {
    await live(b.ctx, frameAt(iso(s), 500));
    counts.push((await storedRows(b.client)).length);
  }

  const c = await createDb();
  const zeroFrame = frameAt(iso(60), 765); // spot near the strikes so byStrike keeps both
  zeroFrame.gamma.net_gex_m = 0;
  zeroFrame.gamma.gamma_flip = null;
  // by_strike already carries a genuine 0 (strike 765) and a null (770).
  await live(c.ctx, frameAt(iso(0), 701));
  await live(c.ctx, zeroFrame); // zero/null frame is the NEWEST -> the fallback
  const cDown = await live(c.ctx, null);

  const d = await createDb();
  const empty = await live(d.ctx, null);
  record(
    "R08",
    "exact replay dedupes; +44 skipped / +45 accepted vs latest persisted instant; 0 stays 0 and null stays null; empty storage honestly empty",
    replayRows === 1 &&
      JSON.stringify(counts) === "[1,1,2,3]" &&
      cDown.staleSnapshot.netGexM === 0 &&
      cDown.staleSnapshot.gammaFlip === null &&
      cDown.staleSnapshot.byStrike[0].netGexM === 0 &&
      cDown.staleSnapshot.byStrike[1].netGexM === null &&
      empty.ok === false &&
      empty.staleSnapshot === null &&
      empty.staleSnapshotAt === null &&
      empty.trail.length === 0,
    { replayRows, gapCounts: counts, emptyOk: empty.ok },
  );
}

import { writeFileSync } from "node:fs";
const outDir = process.argv[2];
if (outDir) {
  writeFileSync(
    outDir + "/r1-cases.json",
    JSON.stringify(
      {
        runtime: "bun " + Bun.version,
        exercised: {
          "server/src/actions.ts": "bundled from this tree at run time; hash attested by the driver",
          storage:
            "drizzle-orm/libsql in-memory; DDL = verbatim drizzle/0002 + drizzle/0003",
        },
        cases,
      },
      null,
      2,
    ) + "\n",
  );
}
console.log("R1AUDIT-BEGIN");
console.log(JSON.stringify({ cases }, null, 2));
console.log("R1AUDIT-END");
