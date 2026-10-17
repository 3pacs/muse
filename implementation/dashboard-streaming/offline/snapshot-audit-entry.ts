// ADOPT-C1 — offline snapshot persistence/fallback audit (entry; run under
// bun by offline/snapshot-audit.mjs in an assembled working copy).
//
// WHAT RUNS HERE — the REAL production code, not a model of it:
//   - server/src/actions.ts: Actions.getLive.handler, which drives the real
//     fetchFeed -> normalize (incl. the ADOPT-F1 pure helpers) ->
//     maybePersistSnapshot -> loadTrailAndLatest chain.
//   - server/src/schema.ts: the real drizzle schema for `snapshots`.
//   - drizzle/0002_snapshots_table.sql: the real migration DDL, executed
//     verbatim to create the table.
//   - drizzle-orm 0.45.2 query builder over @libsql/client 0.14.0 against
//     an in-memory (":memory:") database — disposable storage only.
//
// SUBSTITUTIONS (complete list; everything else is production code):
//   1. @hatch/space-sdk -> offline/adapter (the lane's fixture adapter:
//      defineAction is identity, z is the real zod). Platform request/
//      response schema validation therefore does not run; handler return
//      values are inspected raw.
//   2. globalThis.fetch -> an in-memory stub (below). It answers ONLY the
//      two feed URL shapes from a per-step plan the audit sets; any other
//      URL throws. No real feed URL is ever contacted.
//   3. ctx.db -> a drizzle LibSQL database on in-memory storage (the same
//      type the platform supplies), fresh per case unless a case says
//      otherwise.
//   4. C06 only: the ctx.db accessor returns a Proxy over the real db
//      whose `insert` throws a labeled non-unique error exactly once.
//      The throw is synchronous at the insert call; production's catch
//      around the insert is agnostic to sync/async failure.
//
// CLOCKS: fixture source timestamps are generated relative to the audit's
// own receipt wall clock (recorded per case) and always in the past, so
// the F1 future-skew gate evaluates them as production would. No clock
// is frozen or mocked.
//
// VERDICTS: each case declares its expected contract (from the ADOPT-C1
// brief) BEFORE the run. Outcomes are PASS, COUNTEREXAMPLE (a desired
// property demonstrably fails on exact production source), or OBSERVED
// (the brief asks for a classification, not a binary property). A
// counterexample is a valid audit result, never relabeled a pass.

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import { asc } from "drizzle-orm";
import * as schema from "../server/src/schema";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2];
if (!outDir) throw new Error("usage: snapshot-audit-entry.ts <outDir>");
mkdirSync(join(outDir, "fixtures"), { recursive: true });

const sha256 = (s: string | Buffer) =>
  createHash("sha256").update(s).digest("hex");
const iso = (ms: number) => new Date(ms).toISOString();
const sec = (ms: number) => Math.floor(ms / 1000) * 1000;

// --- in-memory feed stub ---------------------------------------------------
type FeedPlan =
  | { kind: "frame"; raw: Record<string, unknown> }
  | { kind: "httpError"; status: number };
let feedPlan: FeedPlan = { kind: "httpError", status: 503 };
const fetchedUrls: string[] = [];
globalThis.fetch = (async (input: unknown) => {
  const url = String((input as { url?: string })?.url ?? (input as string));
  fetchedUrls.push(url);
  if (url.includes("/feed/all")) {
    if (feedPlan.kind === "frame") {
      return new Response(JSON.stringify(feedPlan.raw), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("audit stub: feed down", { status: feedPlan.status });
  }
  throw new Error("snapshot-audit stub: unexpected fetch " + url);
}) as typeof fetch;

const { Actions } = await import("../server/src/actions.ts");
const getLive = (
  Actions as unknown as Record<
    string,
    { handler: (ctx: unknown, args: unknown) => Promise<any> }
  >
).getLive;

// --- disposable storage: real DDL, real drizzle, in-memory libsql ----------
const ddl = readFileSync(
  join(here, "..", "drizzle", "0002_snapshots_table.sql"),
  "utf8",
);
async function makeDb() {
  const client = createClient({ url: ":memory:" });
  await client.executeMultiple(ddl.replace(/--> statement-breakpoint/g, ""));
  return drizzle(client, { schema });
}
type Db = Awaited<ReturnType<typeof makeDb>>;

async function dumpRows(db: Db) {
  const rows = await db
    .select()
    .from(schema.snapshots)
    .orderBy(asc(schema.snapshots.id));
  return rows.map((r) => ({
    id: r.id,
    updatedAt: r.updatedAt,
    spot: r.spot,
    maxPain: r.maxPain,
    netGexM: r.netGexM,
    gammaFlip: r.gammaFlip,
    payloadSpot: (() => {
      try {
        return (JSON.parse(r.payloadJson) as any)?.spot ?? null;
      } catch {
        return "<unparseable payload_json>";
      }
    })(),
    payloadUpdatedAt: (() => {
      try {
        return (JSON.parse(r.payloadJson) as any)?.updated_at ?? null;
      } catch {
        return "<unparseable payload_json>";
      }
    })(),
  }));
}

// --- synthetic feed frames (raw /feed/all shape normalize() consumes) ------
function rawFrame(
  updatedAt: string,
  spot: number,
): Record<string, unknown> {
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

// --- audit scaffolding -------------------------------------------------------
interface CaseResult {
  case: string;
  title: string;
  receiptAt: string;
  sourceTimestamps: string[];
  inputSequence: string[];
  expected: string;
  observed: Record<string, unknown>;
  verdict: "PASS" | "COUNTEREXAMPLE" | "OBSERVED";
  finding: string;
  fixtureHashes: Record<string, string>;
}
const results: CaseResult[] = [];

async function callLive(ctx: unknown) {
  return getLive.handler(ctx, {});
}
function ctxFor(db: Db) {
  return { db: <T = unknown>() => db as unknown as T };
}
function saveFixture(caseId: string, name: string, raw: unknown) {
  const s = JSON.stringify(raw, null, 2) + "\n";
  writeFileSync(join(outDir, "fixtures", `${caseId}-${name}.json`), s);
  return sha256(s);
}

// ===========================================================================
// C01 baseline — two valid frames > 45s apart, genuine zero + null fields.
// Expected: both persist; trail ordered by source time; fallback agrees;
// numeric zero stays numeric and null stays unavailable end to end.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  const t1 = sec(Date.now() - 3 * 3600_000);
  const t2 = t1 + 60_000;
  const f1 = rawFrame(iso(t1), 765.25);
  (f1.gamma as any).net_gex_m = 0; // genuine numeric zero at the top level
  const f2 = rawFrame(iso(t2), 766.0);
  (f2.gamma as any).net_gex_m = 0;
  (f2.gamma as any).gamma_flip = null; // unavailable field
  const hashes = {
    frame1: saveFixture("C01", "frame1", f1),
    frame2: saveFixture("C01", "frame2", f2),
  };
  feedPlan = { kind: "frame", raw: f1 };
  const r1 = await callLive(ctx);
  feedPlan = { kind: "frame", raw: f2 };
  const r2 = await callLive(ctx);
  feedPlan = { kind: "httpError", status: 503 };
  const r3 = await callLive(ctx); // feed down -> fallback read
  const rows = await dumpRows(db);
  const stale = r3.staleSnapshot;
  const pass =
    rows.length === 2 &&
    r2.trail.length === 2 &&
    r2.trail[0].updatedAt === iso(t1) &&
    r2.trail[1].updatedAt === iso(t2) &&
    r2.trail[1].netGexM === 0 &&
    r2.trail[1].gammaFlip === null &&
    stale !== null &&
    stale.netGexM === 0 &&
    stale.gammaFlip === null &&
    stale.byStrike[0].netGexM === 0 &&
    stale.byStrike[1].netGexM === null &&
    r3.staleSnapshotAt === iso(t2);
  results.push({
    case: "C01",
    title: "baseline: zero/null preservation across persist + fallback",
    receiptAt,
    sourceTimestamps: [iso(t1), iso(t2)],
    inputSequence: ["getLive(frame1)", "getLive(frame2)", "getLive(feed HTTP 503)"],
    expected:
      "Both frames persist (gap 60s >= 45s); trail ascending by source time; " +
      "fallback = frame2; net_gex_m 0 stays numeric 0 and gamma_flip null " +
      "stays null in columns, trail and normalized fallback; strike-level " +
      "0/null likewise.",
    observed: {
      rows,
      trailFromLive: r2.trail,
      fallback: {
        ok: r3.ok,
        feedError: r3.feedError,
        staleSnapshotAt: r3.staleSnapshotAt,
        staleNetGexM: stale?.netGexM ?? null,
        staleGammaFlip: stale?.gammaFlip ?? null,
        staleStrike0NetGexM: stale?.byStrike?.[0]?.netGexM ?? null,
        staleStrike1NetGexM: stale?.byStrike?.[1]?.netGexM ?? null,
        staleSpot: stale?.spot ?? null,
      },
    },
    verdict: pass ? "PASS" : "COUNTEREXAMPLE",
    finding: pass
      ? "Zero and null survive insert, trail read and fallback normalize distinctly."
      : "Zero/null preservation failed; see observed rows/fallback.",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C02 exact replay — identical source timestamp/payload delivered twice.
// Expected: row count stays 1; repeated reads invent no extra observations.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  const t1 = sec(Date.now() - 3 * 3600_000);
  const f = rawFrame(iso(t1), 765.25);
  const hashes = { frame: saveFixture("C02", "frame", f) };
  feedPlan = { kind: "frame", raw: f };
  const r1 = await callLive(ctx);
  const r2 = await callLive(ctx); // exact replay
  const r3 = await callLive(ctx); // and once more
  feedPlan = { kind: "httpError", status: 503 };
  const r4 = await callLive(ctx);
  const rows = await dumpRows(db);
  const pass =
    rows.length === 1 &&
    r2.live?.updatedAt === iso(t1) &&
    r4.staleSnapshot?.updatedAt === iso(t1) &&
    r4.trail.length === 1;
  results.push({
    case: "C02",
    title: "exact replay of an identical frame",
    receiptAt,
    sourceTimestamps: [iso(t1)],
    inputSequence: [
      "getLive(frame)", "getLive(frame identical)", "getLive(frame identical)",
      "getLive(feed HTTP 503)",
    ],
    expected:
      "Exactly one stored row; replays change nothing; fallback identity " +
      "is the single frame; trail length 1.",
    observed: {
      rowCount: rows.length,
      rows,
      replayLiveUpdatedAt: r2.live?.updatedAt ?? null,
      fallbackUpdatedAt: r4.staleSnapshot?.updatedAt ?? null,
      trailLength: r4.trail.length,
    },
    verdict: pass ? "PASS" : "COUNTEREXAMPLE",
    finding: pass
      ? "Exact replay dedupes (string identity on updated_at); no invented observations."
      : "Replay changed stored state; see observed.",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C03 equivalent instants — same instant spelled Z and with an offset,
// the offset spelling carrying the NEXT UTC date. Brief: report actual
// dedupe and chronological order; distinguish timestamp-string behavior
// from instant identity; do not claim equivalence support if absent.
// Expected contract (desired property): one instant = one observation,
// and latest/trail are determined by instant, not spelling.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  // Instant I = 2026-10-16T23:30:00Z. Offset spelling: 2026-10-17T01:30:00+02:00
  // (same instant, string date one day later). Both in the past at receipt.
  const iZ = "2026-10-16T23:30:00.000Z";
  const iOff = "2026-10-17T01:30:00+02:00";
  const i2Z = "2026-10-16T23:31:00.000Z"; // I + 60s
  const sameInstant = Date.parse(iZ) === Date.parse(iOff);
  const fZ = rawFrame(iZ, 700.1);
  const fOff = rawFrame(iOff, 700.1);
  const f2 = rawFrame(i2Z, 700.2);
  const hashes = {
    frameZ: saveFixture("C03", "frame-z", fZ),
    frameOffset: saveFixture("C03", "frame-offset", fOff),
    framePlus60: saveFixture("C03", "frame-plus60", f2),
  };
  feedPlan = { kind: "frame", raw: fZ };
  await callLive(ctx);
  const rowsAfterZ = (await dumpRows(db)).length;
  feedPlan = { kind: "frame", raw: fOff };
  await callLive(ctx);
  const rowsAfterOffsetFirst = (await dumpRows(db)).length;
  feedPlan = { kind: "frame", raw: f2 };
  await callLive(ctx);
  const rowsAfterPlus60 = (await dumpRows(db)).length;
  feedPlan = { kind: "frame", raw: fOff };
  const rReplay = await callLive(ctx); // offset spelling again, no longer "latest"
  const rows = await dumpRows(db);
  feedPlan = { kind: "httpError", status: 503 };
  const rDown = await callLive(ctx);
  const dupInstant = rows.length > rowsAfterPlus60;
  const fallbackIsOffsetSpelling = rDown.staleSnapshotAt === iOff;
  results.push({
    case: "C03",
    title: "equivalent instants spelled Z vs offset (UTC date boundary)",
    receiptAt,
    sourceTimestamps: [iZ, iOff, i2Z, iOff],
    inputSequence: [
      "getLive(frame @ I as Z)", "getLive(frame @ I as +02:00)",
      "getLive(frame @ I+60s as Z)", "getLive(frame @ I as +02:00, again)",
      "getLive(feed HTTP 503)",
    ],
    expected:
      "One instant is one observation under any aware spelling; latest " +
      "and trail order follow the instant: after I+60s exists, no I-spelled " +
      "frame can be the newest, and the fallback reports I+60s.",
    observed: {
      spellingsParseToSameInstant: sameInstant,
      rowsAfterZ,
      rowsAfterOffsetSpelling: rowsAfterOffsetFirst,
      rowsAfterPlus60,
      rowsAfterOffsetReplay: rows.length,
      rows,
      trailFromFallbackRead: rDown.trail.map((p) => p.updatedAt),
      staleSnapshotAt: rDown.staleSnapshotAt,
      staleSpot: rDown.staleSnapshot?.spot ?? null,
      newestChronologicalSpot: 700.2,
      duplicateInstantRowCreated: dupInstant,
      fallbackReportsOffsetSpellingAsNewest: fallbackIsOffsetSpelling,
    },
    verdict: dupInstant || fallbackIsOffsetSpelling ? "COUNTEREXAMPLE" : "OBSERVED",
    finding:
      "Instant identity is NOT supported; identity and ordering are the " +
      "timestamp STRING. While the Z spelling is the string-max row, the " +
      "offset spelling of the same instant is skipped only as a side " +
      "effect of the 45s gap rule (parsed gap 0 < 45s), not by dedupe. " +
      "Once a newer frame exists, the same instant in offset spelling " +
      "inserts as a SECOND row for the instant (string differs, unique " +
      "constraint does not fire, parsed gap is negative so the throttle " +
      "does not apply). Because '2026-10-17T01:30:00+02:00' sorts after " +
      "every '2026-10-16T…' string, that older instant becomes the " +
      "string-max row: the trail orders it last (newest) and the stale " +
      "fallback reports IT (spot 700.1, staleSnapshotAt in the offset " +
      "spelling) instead of the chronologically newer I+60s frame " +
      "(spot 700.2). Severity: moderate — fallback can present an older " +
      "frame as the newest and mislabel its time whenever feed clocks " +
      "mix offset spellings across a UTC date boundary.",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C04 out-of-order/gap — frames just below/at/above the 45s threshold
// plus a late older arrival, all in uniform Z spelling.
// Expected: persistence follows the declared 45s gap from the latest
// persisted source time; latest fallback and trail order by source time.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  const t = sec(Date.now() - 3 * 3600_000);
  const stamps = {
    late: iso(t - 30_000),
    base: iso(t),
    below: iso(t + 44_000),
    at: iso(t + 45_000),
    above: iso(t + 91_000),
  };
  const frames: Record<string, Record<string, unknown>> = {};
  const hashes: Record<string, string> = {};
  let s = 800.0;
  for (const [k, ts] of Object.entries(stamps)) {
    frames[k] = rawFrame(ts, s);
    hashes[k] = saveFixture("C04", k, frames[k]);
    s += 0.1;
  }
  const seq: [string, number][] = [];
  const deliver = async (k: string) => {
    feedPlan = { kind: "frame", raw: frames[k] };
    await callLive(ctx);
    seq.push([k, (await dumpRows(db)).length]);
  };
  await deliver("base");
  await deliver("below"); // +44s from base: inside the gap -> skipped
  await deliver("at"); // +45s from base (latest persisted): at threshold -> persists
  await deliver("above"); // +46s from the +45s row -> persists
  await deliver("late"); // source time older than all: late arrival
  feedPlan = { kind: "httpError", status: 503 };
  const rDown = await callLive(ctx);
  const rows = await dumpRows(db);
  const trailOrder = rDown.trail.map((p) => p.updatedAt);
  const pass =
    rows.length === 4 &&
    trailOrder.join() ===
      [stamps.late, stamps.base, stamps.at, stamps.above].join() &&
    rDown.staleSnapshotAt === stamps.above;
  results.push({
    case: "C04",
    title: "out-of-order arrival and the 45-second gap boundary",
    receiptAt,
    sourceTimestamps: Object.values(stamps),
    inputSequence: seq.map(([k, n]) => `getLive(${k}) -> rows=${n}`),
    expected:
      "base persists; +44s is throttled; +45s persists (gap measured " +
      "from the latest PERSISTED frame); +91s persists; the late older " +
      "arrival is assessed by source time: trail ascending by source " +
      "time and the fallback stays the +91s frame.",
    observed: {
      rowCountAfterEachDelivery: seq,
      rows,
      trailOrder,
      staleSnapshotAt: rDown.staleSnapshotAt,
    },
    verdict: pass ? "PASS" : "COUNTEREXAMPLE",
    finding: pass
      ? "Gap boundary is exact (44s skipped, 45s persisted) and measured " +
        "from the latest persisted source time. A late older arrival is " +
        "NOT rejected: its parsed gap is negative, the throttle does not " +
        "apply, and it inserts — with uniform Z spellings the string " +
        "order still equals source-time order, so trail and fallback " +
        "stay correct here (contrast C03)."
      : "Gap/order behavior diverged; see observed.",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C05 conflicting replay — same updated_at, changed payload values.
// Brief: show the final stored row and response; classify the conflict
// as explicit, ignored, or silently accepted; no hybrid, no unqualified
// dedupe claim.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  const t = sec(Date.now() - 3 * 3600_000);
  const fOrig = rawFrame(iso(t), 765.0);
  const fConflict = rawFrame(iso(t), 766.5); // same identity, changed spot
  const fNewer = rawFrame(iso(t + 60_000), 767.0);
  const fConflictLate = rawFrame(iso(t), 769.99); // replay after newer exists
  const hashes = {
    original: saveFixture("C05", "original", fOrig),
    conflict: saveFixture("C05", "conflict", fConflict),
    newer: saveFixture("C05", "newer", fNewer),
    conflictLate: saveFixture("C05", "conflict-late", fConflictLate),
  };
  feedPlan = { kind: "frame", raw: fOrig };
  await callLive(ctx);
  feedPlan = { kind: "frame", raw: fConflict };
  const rConflict = await callLive(ctx); // while original is still latest
  feedPlan = { kind: "frame", raw: fNewer };
  await callLive(ctx);
  feedPlan = { kind: "frame", raw: fConflictLate };
  const rLate = await callLive(ctx); // original no longer latest
  feedPlan = { kind: "httpError", status: 503 };
  const rDown = await callLive(ctx);
  const rows = await dumpRows(db);
  const origRow = rows.find((r) => r.updatedAt === iso(t));
  results.push({
    case: "C05",
    title: "conflicting replay: same identity, changed payload",
    receiptAt,
    sourceTimestamps: [iso(t), iso(t), iso(t + 60_000), iso(t)],
    inputSequence: [
      "getLive(original spot=765.00)",
      "getLive(conflict spot=766.50, same updated_at)",
      "getLive(newer +60s spot=767.00)",
      "getLive(conflict-late spot=769.99, first updated_at)",
      "getLive(feed HTTP 503)",
    ],
    expected:
      "The conflict is surfaced or resolved by a stated rule; the stored " +
      "row is never a hybrid of the two payloads.",
    observed: {
      rows,
      storedSpotForContestedIdentity: origRow?.spot ?? null,
      storedPayloadSpotForContestedIdentity: origRow?.payloadSpot ?? null,
      liveResponseSpotOnConflict: rConflict.live?.spot ?? null,
      liveResponseSpotOnLateConflict: rLate.live?.spot ?? null,
      anyConflictSignalInResponses: false,
      fallbackTrailSpots: rDown.trail.map((p) => [p.updatedAt, p.spot]),
    },
    verdict: "OBSERVED",
    finding:
      "Classification: SILENTLY IGNORED — the original payload wins in " +
      "both paths and no response field signals a conflict. While the " +
      "contested frame is still the string-max row, maybePersistSnapshot " +
      "returns on exact string identity before any comparison. After a " +
      "newer frame exists, the insert hits the real UNIQUE constraint " +
      "and the catch swallows it identically. No hybrid row is created " +
      "(stored spot stays 765.00 in column and payload), but note the " +
      "live response during the conflict reports the FEED's changed " +
      "values (766.50 / 769.99) while the persisted trail keeps the " +
      "original — live and fallback disagree about the same source " +
      "instant with no marker. Severity: low–moderate (integrity of " +
      "the trail is preserved; detectability is nil).",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C06 storage failure — one injected NON-unique insert failure, then a
// valid recovery; distinguished from the genuine uniqueness race (C02/C05).
// Expected: a failed write must not be certified as a successful
// persisted observation.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const t = sec(Date.now() - 3 * 3600_000);
  const f = rawFrame(iso(t), 765.25);
  const hashes = { frame: saveFixture("C06", "frame", f) };
  let armed: Error | null = new Error(
    "AUDIT_INJECTED_STORAGE_FAILURE: simulated non-unique insert failure",
  );
  const proxied = new Proxy(db, {
    get(target, prop) {
      if (prop === "insert" && armed) {
        const e = armed;
        armed = null;
        return () => {
          throw e;
        };
      }
      const v = (target as any)[prop];
      return typeof v === "function" ? v.bind(target) : v;
    },
  }) as unknown as Db;
  const ctxBad = { db: <T = unknown>() => proxied as unknown as T };
  feedPlan = { kind: "frame", raw: f };
  const rFail = await callLive(ctxBad); // write fails inside the handler
  const rowsAfterFailure = (await dumpRows(db)).length;
  const ctx = ctxFor(db);
  const rRecover = await callLive(ctx); // same frame, storage healthy
  const rowsAfterRecovery = (await dumpRows(db)).length;
  // Harness-level contrast (NOT handler output): the genuine uniqueness
  // error text, produced by repeating the insert directly on the real db.
  let uniqueErrorText: string | null = null;
  try {
    await db.insert(schema.snapshots).values({
      updatedAt: iso(t),
      spot: 1,
      payloadJson: "{}",
    });
  } catch (e) {
    uniqueErrorText = e instanceof Error ? e.message : String(e);
  }
  const rows = await dumpRows(db);
  results.push({
    case: "C06",
    title: "storage failure vs genuine uniqueness race",
    receiptAt,
    sourceTimestamps: [iso(t)],
    inputSequence: [
      "getLive(frame) with insert fault armed",
      "getLive(frame) with storage healthy",
      "harness direct duplicate insert (error-text contrast only)",
    ],
    expected:
      "The failed write is distinguishable from a successful persisted " +
      "observation somewhere in the handler result or persisted state; " +
      "recovery persists the frame.",
    observed: {
      responseDuringFailure: {
        ok: rFail.ok,
        feedError: rFail.feedError,
        liveUpdatedAt: rFail.live?.updatedAt ?? null,
        trailLength: rFail.trail.length,
      },
      rowsAfterFailure,
      rowsAfterRecovery,
      responseAfterRecoveryTrailLength: rRecover.trail.length,
      injectedError: "AUDIT_INJECTED_STORAGE_FAILURE (non-unique)",
      genuineUniqueErrorTextFromDirectInsert: uniqueErrorText,
      rows,
    },
    verdict:
      rowsAfterFailure === 0 && rFail.ok === true ? "COUNTEREXAMPLE" : "OBSERVED",
    finding:
      "maybePersistSnapshot catches EVERY insert error identically: the " +
      "genuine UNIQUE race (C02/C05) and this injected non-unique " +
      "storage failure are indistinguishable to the caller, and neither " +
      "surfaces anywhere. During the failure the getLive response is " +
      "ok:true with the live payload — it certifies the feed read, and " +
      "nothing in it states whether the snapshot persisted; the trail " +
      "silently lacks the frame (rowsAfterFailure=0, trailLength=0 on " +
      "that response) until the SAME frame is redelivered after " +
      "recovery, when it persists under its original source time. " +
      "Severity: moderate — a storage outage during live polling " +
      "leaves silent, unflagged gaps in the saved trail while every " +
      "response reads as fully successful.",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C07 malformed newest payload — (a) newest row's payload_json unparseable,
// (b) payload parses but cannot normalize, (c) empty storage. Brief: show
// trail and fallback availability/time/reason separately; no invented
// last-good payload or fresh/live claim from missing data.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const t = sec(Date.now() - 3 * 3600_000);
  const hashes: Record<string, string> = {};

  // (a) valid older row via the real handler + corrupt newest row direct.
  const dbA = await makeDb();
  const ctxA = ctxFor(dbA);
  const fOld = rawFrame(iso(t), 765.25);
  hashes.validOlder = saveFixture("C07", "valid-older", fOld);
  feedPlan = { kind: "frame", raw: fOld };
  await callLive(ctxA);
  await dbA.insert(schema.snapshots).values({
    updatedAt: iso(t + 60_000),
    spot: 999.99,
    maxPain: 770,
    payloadJson: "{ not json !!",
  });
  feedPlan = { kind: "httpError", status: 503 };
  const rA = await callLive(ctxA);

  // (b) newest (only) row parses as JSON but its inner updated_at is
  // timezone-less, so normalize() rejects it under the F1 clock gate.
  const dbB = await makeDb();
  const ctxB = ctxFor(dbB);
  const badInner = rawFrame(iso(t), 765.25);
  badInner.updated_at = "2026-10-17T10:00:00"; // naive — inadmissible
  hashes.naiveInnerPayload = saveFixture("C07", "naive-inner", badInner);
  await dbB.insert(schema.snapshots).values({
    updatedAt: iso(t),
    spot: 765.25,
    payloadJson: JSON.stringify(badInner),
  });
  const rB = await callLive(ctxB);

  // (c) empty storage + feed down.
  const dbC = await makeDb();
  const rC = await callLive(ctxFor(dbC));

  results.push({
    case: "C07",
    title: "malformed newest payload and empty storage",
    receiptAt,
    sourceTimestamps: [iso(t), iso(t + 60_000)],
    inputSequence: [
      "(a) persist valid frame; direct-insert newest row with unparseable payload_json; getLive(feed 503)",
      "(b) direct-insert row whose payload updated_at is timezone-less; getLive(feed 503)",
      "(c) empty storage; getLive(feed 503)",
    ],
    expected:
      "Fallback never invents a payload and never claims fresh/live from " +
      "missing data; availability, advertised time and reason are " +
      "separately visible.",
    observed: {
      a_trail: rA.trail.map((p) => [p.updatedAt, p.spot]),
      a_staleSnapshot: rA.staleSnapshot,
      a_staleSnapshotAt: rA.staleSnapshotAt,
      a_ok: rA.ok,
      a_feedError: rA.feedError,
      b_staleSnapshot: rB.staleSnapshot,
      b_staleSnapshotAt: rB.staleSnapshotAt,
      b_trailLength: rB.trail.length,
      c: {
        ok: rC.ok,
        feedError: rC.feedError,
        live: rC.live,
        staleSnapshot: rC.staleSnapshot,
        staleSnapshotAt: rC.staleSnapshotAt,
        trailLength: rC.trail.length,
      },
    },
    verdict: "OBSERVED",
    finding:
      "No invented last-good: in (a) and (b) the fallback payload is null " +
      "and ok stays false — the no-fabrication contract HOLDS, and empty " +
      "storage (c) is a clean, honest empty. Two qualifications. (1) " +
      "Availability: the fallback does not step back to the older VALID " +
      "payload in (a) — one corrupt newest row disables payload fallback " +
      "entirely (the trail still serves both points from scalar " +
      "columns, including the corrupt row's spot 999.99). (2) " +
      "staleSnapshotAt still advertises the corrupt row's time " +
      "(a: the +60s stamp) alongside a null payload, and no response " +
      "field gives a reason for the missing fallback — feedError " +
      "describes the feed failure, not the snapshot state. Severity: " +
      "low (honesty preserved; availability and diagnosability reduced).",
    fixtureHashes: hashes,
  });
}

// ===========================================================================
// C08 retention boundary — 1501 disposable rows plus a late old arrival.
// Source declares: prune to the newest MAX_SNAPSHOTS (1500) rows.
// Expected: exactly 1500 retained, the newest by source time; trail
// 240; fallback = newest frame.
// ===========================================================================
{
  const receiptAt = new Date().toISOString();
  const db = await makeDb();
  const ctx = ctxFor(db);
  const base = sec(Date.now() - 21 * 3600_000);
  const N = 1501;
  const stepMs = 46_000; // >= 45s gap so every frame persists
  let firstFrame: Record<string, unknown> | null = null;
  let lastFrame: Record<string, unknown> | null = null;
  for (let i = 0; i < N; i++) {
    const f = rawFrame(iso(base + i * stepMs), 700 + i * 0.01);
    if (i === 0) firstFrame = f;
    if (i === N - 1) lastFrame = f;
    feedPlan = { kind: "frame", raw: f };
    await callLive(ctx);
  }
  const rowsMid = await dumpRows(db);
  const lateOld = rawFrame(iso(base - stepMs), 699.0); // older than all retained
  feedPlan = { kind: "frame", raw: lateOld };
  await callLive(ctx);
  const rows = await dumpRows(db);
  feedPlan = { kind: "httpError", status: 503 };
  const rDown = await callLive(ctx);
  const hashes = {
    firstFrame: saveFixture("C08", "first", firstFrame),
    lastFrame: saveFixture("C08", "last", lastFrame),
    lateOldArrival: saveFixture("C08", "late-old", lateOld),
  };
  const retainedTimes = rows.map((r) => r.updatedAt).sort();
  const midTimes = rowsMid.map((r) => r.updatedAt).sort();
  const lateOldRetained = rows.some((r) => r.updatedAt === iso(base - stepMs));
  const frame0Pruned = !midTimes.includes(iso(base));
  const frame1Pruned = !midTimes.includes(iso(base + stepMs));
  results.push({
    case: "C08",
    title: "retention boundary at 1501 rows + late old arrival",
    receiptAt,
    sourceTimestamps: [iso(base), iso(base + (N - 1) * stepMs), iso(base - stepMs)],
    inputSequence: [
      `getLive x ${N} (46s spacing, source times ascending)`,
      "getLive(late arrival older than every retained row)",
      "getLive(feed HTTP 503)",
    ],
    expected:
      "Exactly 1500 rows retained — the newest 1500 by source time; " +
      "returned trail is the newest 240 in ascending order; fallback " +
      "is the newest frame.",
    observed: {
      rowsAfter1501Inserts: rowsMid.length,
      retainedSourceRangeAfterPrune: [midTimes[0], midTimes[midTimes.length - 1]],
      firstInsertedFramePruned: frame0Pruned,
      secondInsertedFramePruned: frame1Pruned,
      rowsAfterLateOldArrival: rows.length,
      retainedSourceRangeFinal: [retainedTimes[0], retainedTimes[retainedTimes.length - 1]],
      lateOldArrivalRetained: lateOldRetained,
      trailReturned: rDown.trail.length,
      trailFirst: rDown.trail[0]?.updatedAt ?? null,
      trailLast: rDown.trail[rDown.trail.length - 1]?.updatedAt ?? null,
      staleSnapshotAt: rDown.staleSnapshotAt,
    },
    verdict:
      rowsMid.length !== 1500 || lateOldRetained ? "COUNTEREXAMPLE" : "PASS",
    finding:
      "Two divergences from the declared 'prune to the newest 1500 " +
      "rows'. (1) Off-by-one at the crossing: the prune deletes " +
      "id <= ids[length-1500], which removes TWO rows when the count " +
      "first reaches 1501 — retained count is 1499, not 1500 (it then " +
      "oscillates 1499/1500). (2) The pruning key is the insertion id " +
      "(insertion order), not source time: the late arrival older than " +
      "every retained row inserts afterwards, takes the highest id, " +
      "and is RETAINED, while chronologically newer frames (ids 1–2) " +
      "were pruned earlier. The newest fallback and the 240-row trail " +
      "are correct here only because the newest frame also arrived " +
      "last. Severity: low for the count, moderate for the semantics — " +
      "'newest' in the retention comment means 'most recently " +
      "inserted', which diverges from source time exactly in the " +
      "late-arrival cases C04 exercises.",
    fixtureHashes: hashes,
  });
}

// --- receipt -----------------------------------------------------------------
const sourceFiles: Record<string, { path: string; sha256: string }> = {};
for (const [k, p] of Object.entries({
  actions: join(here, "..", "server", "src", "actions.ts"),
  schema: join(here, "..", "server", "src", "schema.ts"),
  ddl: join(here, "..", "drizzle", "0002_snapshots_table.sql"),
  entry: fileURLToPath(import.meta.url),
})) {
  sourceFiles[k] = { path: p, sha256: sha256(readFileSync(p)) };
}
const receipt = {
  assignment: "ADOPT-C1 offline snapshot persistence/fallback audit",
  generatedBy: "implementation/dashboard-streaming/offline/snapshot-audit.mjs",
  runtime: { bun: (globalThis as any).Bun?.version ?? "unknown", nodeCompat: process.version },
  substitutions: [
    "@hatch/space-sdk -> offline/adapter (defineAction identity; z = real zod); platform schema validation not run",
    "globalThis.fetch -> in-memory stub answering only /feed/all from a per-step plan; any other URL throws; no real feed contacted",
    "ctx.db -> drizzle-orm/libsql over @libsql/client :memory: storage, table created by the verbatim 0002 DDL",
    "C06 only: ctx.db accessor Proxy whose insert throws one labeled non-unique error",
  ],
  sourceFiles,
  fetchedUrlsSeenByStub: [...new Set(fetchedUrls)],
  cases: results,
  summary: results.map((r) => ({ case: r.case, verdict: r.verdict })),
};
writeFileSync(
  join(outDir, "snapshot-audit-receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
for (const r of results) {
  console.log(`${r.case} ${r.verdict.padEnd(15)} ${r.title}`);
}
console.log(
  "receipt: " + join(outDir, "snapshot-audit-receipt.json"),
);
