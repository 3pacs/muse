// Actions for the 0DTE Streaming Dashboard.
//
// The live source is the interpreter service (~/workspace/stepdad-0dte/
// interpreter.py) running on this host at :8787. It polls
// gex.stepdad.finance (/api/state + /api/contracts) and Nasdaq's public
// option-chain API and publishes a combined snapshot at /feed/all every
// ~30s, plus an SSE /stream. This artifact never rebuilds or republishes:
// while the page is open the client polls `getLive` every 15s and the
// numbers update in place.
//
// All feed access is server-side: the browser never fetches the http feed
// directly (mixed content from the https shell, and localhost is
// meaningless on the trader's phone). On any feed failure the action
// returns the last persisted snapshot labeled stale — never invented data.

import {
defineAction,
z,
type ActionsModule,
type Ctx,
} from "@hatch/space-sdk";
import { and, desc, eq, isNotNull, isNull, lt, or } from "drizzle-orm";
import * as schema from "./schema";

// ---------------------------------------------------------------------------
// Normalized live payload — the only shape the client renders.
// Every market field is nullable: the feed honestly omits some values
// (e.g. 25d risk reversal) and the UI renders those as unavailable.
// ---------------------------------------------------------------------------

const strikeGex = z.object({
  strike: z.number(),
  // ADOPT-F1: nullable on purpose — a strike whose GEX the feed did not
  // report is "unavailable", never a fabricated 0. Genuine zeros reported
  // by the feed remain 0.
  netGexM: z.number().nullable(),
  callGexM: z.number().nullable(),
  putGexM: z.number().nullable(),
  src: z.string().nullable(),
});

const activityRow = z.object({
  strike: z.number(),
  side: z.string(),
  volume: z.number().nullable(),
  oi: z.number().nullable(),
  volOi: z.number().nullable(),
  notionalK: z.number().nullable(),
  src: z.string().nullable(),
});

const livePayload = z.object({
  status: z.string(),
  updatedAt: z.string(),
  quoteAsOf: z.string().nullable(),
  marketOpen: z.boolean(),
  spot: z.number().nullable(),
  expiry: z.string().nullable(),
  netGexM: z.number().nullable(),
  gammaFlip: z.number().nullable(),
  callWall: z.number().nullable(),
  putWall: z.number().nullable(),
  maxPain: z.number().nullable(),
  regime: z.string().nullable(),
  pinScore: z.number().nullable(),
  pinMagnet: z.number().nullable(),
  pinComponents: z
    .object({
      concentration: z.number().nullable(),
      proximity: z.number().nullable(),
      timeElapsed: z.number().nullable(),
    })
    .nullable(),
  expectedMoveDollars: z.number().nullable(),
  expectedMovePct: z.number().nullable(),
  expectedMoveRemaining: z.number().nullable(),
  hedgeBuckets: z.array(
    z.object({
      shockBp: z.number(),
      dS: z.number().nullable(),
      notionalM: z.number().nullable(),
      direction: z.string().nullable(),
    }),
  ),
  dealerGammaPerPtM: z.number().nullable(),
  speedMPerPt2: z.number().nullable(),
  speedWideMPerPt2: z.number().nullable(),
  reversalConditions: z.array(z.string()),
  reversalStretched: z.boolean().nullable(),
  pcVolume: z.number().nullable(),
  pcOi: z.number().nullable(),
  callVolume: z.number().nullable(),
  putVolume: z.number().nullable(),
  atmCallIv: z.number().nullable(),
  atmPutIv: z.number().nullable(),
  riskReversal25d: z.number().nullable(),
  totalVannaK: z.number().nullable(),
  totalCharmK: z.number().nullable(),
  byStrike: z.array(strikeGex),
  topStrikes: z.array(strikeGex),
  // ADOPT-F1: coverage evidence for byStrike — how many strikes carried a
  // reported net GEX (genuine zeros count as known) vs unavailable.
  strikeCoverage: z
    .object({
      total: z.number(),
      gexKnown: z.number(),
      gexMissing: z.number(),
    })
    .nullable(),
  elevatedActivity: z.array(activityRow),
  rtdStrikes: z.number().nullable(),
  nasdaqStrikes: z.number().nullable(),
  nasdaqAsOf: z.string().nullable(),
  nasdaqStale: z.boolean().nullable(),
});

type LivePayload = z.infer<typeof livePayload>;

const trailPoint = z.object({
  updatedAt: z.string(),
  spot: z.number().nullable(),
  callWall: z.number().nullable(),
  putWall: z.number().nullable(),
  gammaFlip: z.number().nullable(),
  maxPain: z.number().nullable(),
  pinScore: z.number().nullable(),
  netGexM: z.number().nullable(),
});

const getLiveResponse = z.object({
  ok: z.boolean(),
  feedError: z.string().nullable(),
  fetchedAt: z.string(),
  live: livePayload.nullable(),
  staleSnapshot: livePayload.nullable(),
  staleSnapshotAt: z.string().nullable(),
  trail: z.array(trailPoint),
});

type GetLiveResponse = z.infer<typeof getLiveResponse>;

// ---------------------------------------------------------------------------
// Signals payload — GET /feed/signals on the same interpreter host. The
// signal layer (loaded-gun state, charm trigger, indicator stacks, extremes
// and share prints) is computed by the interpreter from tape.db; this
// artifact only renders it. Any failure here must never break the main
// feed: the client gets signals: null and shows a muted note.
// ---------------------------------------------------------------------------

const signalsPayload = z.object({
  status: z.string(),
  day: z.string().nullable(),
  generatedAt: z.string().nullable(),
  loadedGun: z.object({
    active: z.boolean(),
    sinceEt: z.string().nullable(),
    spot: z.number().nullable(),
    budgetLeft: z.number().nullable(),
    pin: z.number().nullable(),
    netGexM: z.number().nullable(),
    flipDist: z.number().nullable(),
  }),
  lastCharmTrigger: z
    .object({
      tsEt: z.string().nullable(),
      spot: z.number().nullable(),
      charmVel30: z.number().nullable(),
    })
    .nullable(),
  stacks: z.array(
    z.object({
      tsEt: z.string().nullable(),
      symbol: z.string(),
      direction: z.string().nullable(),
      spot: z.number().nullable(),
      members: z.array(z.string()),
      path: z.string().nullable(),
    }),
  ),
  extremes: z.array(
    z.object({
      tsEt: z.string().nullable(),
      symbol: z.string(),
      type: z.string(),
      direction: z.string().nullable(),
      spot: z.number().nullable(),
      vol: z.number().nullable(),
      mult: z.number().nullable(),
      mega: z.boolean().nullable(),
      cluster: z.boolean().nullable(),
      prints60m: z.number().nullable(),
      atLows: z.boolean().nullable(),
      atHighs: z.boolean().nullable(),
    }),
  ),
});

type SignalsPayload = z.infer<typeof signalsPayload>;

const getSignalsResponse = z.object({
  ok: z.boolean(),
  signals: signalsPayload.nullable(),
});

type GetSignalsResponse = z.infer<typeof getSignalsResponse>;

function boolOrNull(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}

function normalizeSignals(raw: Record<string, unknown>): SignalsPayload | null {
  if (str(raw["status"]) !== "ok") return null;
  const gun = obj(raw["loaded_gun"]);
  const charmRaw = raw["last_charm_trigger"];
  const charm = charmRaw === null || charmRaw === undefined ? null : obj(charmRaw);

  const stacks: SignalsPayload["stacks"] = [];
  if (Array.isArray(raw["stacks"])) {
    for (const row of raw["stacks"]) {
      const r = obj(row);
      const detail = obj(r["detail"]);
      stacks.push({
        tsEt: str(r["ts_et"]),
        symbol: str(r["symbol"]) ?? "?",
        direction: str(r["direction"]),
        spot: num(r["spot"]),
        members: Array.isArray(detail["members"])
          ? detail["members"].filter(
              (m): m is string => typeof m === "string",
            )
          : [],
        path: str(detail["path"]),
      });
    }
  }

  const extremes: SignalsPayload["extremes"] = [];
  if (Array.isArray(raw["extremes"])) {
    for (const row of raw["extremes"]) {
      const r = obj(row);
      const detail = obj(r["detail"]);
      extremes.push({
        tsEt: str(r["ts_et"]),
        symbol: str(r["symbol"]) ?? "?",
        type: str(r["type"]) ?? "?",
        direction: str(r["direction"]),
        spot: num(r["spot"]),
        vol: num(detail["vol"]),
        mult: num(detail["mult"]),
        mega: boolOrNull(detail["mega"]),
        cluster: boolOrNull(detail["cluster"]),
        prints60m: num(detail["prints_60m"]),
        atLows: boolOrNull(detail["at_lows"]),
        atHighs: boolOrNull(detail["at_highs"]),
      });
    }
  }

  return {
    status: "ok",
    day: str(raw["day"]),
    generatedAt: str(raw["generated_at"]),
    loadedGun: {
      active: gun["active"] === true,
      sinceEt: str(gun["since_et"]),
      spot: num(gun["spot"]),
      budgetLeft: num(gun["budget_left"]),
      pin: num(gun["pin"]),
      netGexM: num(gun["net_gex_m"]),
      flipDist: num(gun["flip_dist"]),
    },
    lastCharmTrigger:
      charm === null
        ? null
        : {
            tsEt: str(charm["ts_et"]),
            spot: num(charm["spot"]),
            charmVel30: num(charm["charm_vel30"]),
          },
    stacks,
    extremes,
  };
}

const SIGNALS_URLS = [
  "http://127.0.0.1:8787/feed/signals",
  "http://gex.stepdad.finance/feed/signals",
];

async function fetchSignals(): Promise<SignalsPayload | null> {
  for (const url of SIGNALS_URLS) {
    try {
      const resp = await fetch(url, {
        headers: { "User-Agent": "muse-0dte-streaming-dashboard/1.0" },
        signal: AbortSignal.timeout(9000),
      });
      if (!resp.ok) continue;
      const raw = (await resp.json()) as Record<string, unknown>;
      const normalized = normalizeSignals(raw);
      if (normalized) return normalized;
    } catch {
      // Signals are best-effort; fall through to the next URL / null.
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Feed fetch + normalization
// ---------------------------------------------------------------------------

const FEED_URLS = [
  "http://127.0.0.1:8787/feed/all",
  "http://gex.stepdad.finance/feed/all",
];

// === ADOPT-F1 PURE HELPERS =================================================
// This block is extracted verbatim by tests/boundaries.test.mjs and run
// offline. Keep it free of imports, module state and I/O.
// ===========================================================================
function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function obj(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null
    ? (v as Record<string, unknown>)
    : {};
}

function mapStrikes(v: unknown): z.infer<typeof strikeGex>[] {
  if (!Array.isArray(v)) return [];
  const out: z.infer<typeof strikeGex>[] = [];
  for (const row of v) {
    const r = obj(row);
    const strike = num(r["strike"]);
    if (strike === null) continue;
    // ADOPT-F1: missing/null/non-numeric GEX stays null (unavailable).
    // Only a value the feed actually reported — including a genuine 0 —
    // becomes a number. Never fabricate zero to fill the field.
    out.push({
      strike,
      netGexM: num(r["net_gex_m"]),
      callGexM: num(r["call_gex_m"]),
      putGexM: num(r["put_gex_m"]),
      src: str(r["src"]),
    });
  }
  return out;
}

// Coverage evidence for a mapped strike array: genuine zeros count as
// known; only null (unreported/invalid) counts as missing.
function strikeCoverage(
  rows: { netGexM: number | null }[],
): { total: number; gexKnown: number; gexMissing: number } {
  let known = 0;
  for (const r of rows) if (r.netGexM !== null) known += 1;
  return { total: rows.length, gexKnown: known, gexMissing: rows.length - known };
}

// Explicit clock-skew allowance for the update (receipt) clock: an
// updated_at up to this far ahead of our clock is treated as skew, not as
// a future-dated frame. Anything further out is inadmissible.
const MAX_FUTURE_SKEW_MS = 120_000;

// Parse an ISO-8601 timestamp ONLY when it carries an explicit timezone
// (Z or ±hh:mm / ±hhmm). A timezone-less string is rejected outright —
// the missing zone is never inferred from the machine locale. Returns
// epoch milliseconds, or null when invalid/naive.
const AWARE_TS_RE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/;
function parseAwareInstant(v: unknown): number | null {
  const s = str(v);
  if (s === null || !AWARE_TS_RE.test(s)) return null;
  const ms = Date.parse(s);
  return Number.isFinite(ms) ? ms : null;
}

// Admission rule for a feed frame's update clock: it must parse as an
// aware instant and must not be meaningfully in the future.
function updateClockAcceptable(v: unknown, nowMs: number): boolean {
  const ms = parseAwareInstant(v);
  if (ms === null) return false;
  return ms - nowMs <= MAX_FUTURE_SKEW_MS;
}
// === END ADOPT-F1 PURE HELPERS ===

function mapActivity(v: unknown): z.infer<typeof activityRow>[] {
  if (!Array.isArray(v)) return [];
  const out: z.infer<typeof activityRow>[] = [];
  for (const row of v.slice(0, 8)) {
    const r = obj(row);
    const strike = num(r["strike"]);
    if (strike === null) continue;
    out.push({
      strike,
      side: str(r["side"]) ?? "?",
      volume: num(r["volume"]),
      oi: num(r["oi"]),
      volOi: num(r["vol_oi"]),
      notionalK: num(r["notional_k"]),
      src: str(r["src"]),
    });
  }
  return out;
}

function normalize(raw: Record<string, unknown>): LivePayload | null {
  const updatedAt = str(raw["updated_at"]);
  // ADOPT-F1: the update (receipt) clock must be a valid timezone-aware
  // timestamp and not meaningfully in the future. A naive, malformed or
  // future-dated updated_at makes the whole frame inadmissible: normalize
  // returns null and the caller keeps serving the last good snapshot
  // rather than presenting this frame as LIVE. (quote_as_of below stays a
  // separate source-observation clock and is not gated by this rule.)
  if (!updatedAt || !updateClockAcceptable(raw["updated_at"], Date.now())) {
    return null;
  }
  const gamma = obj(raw["gamma"]);
  const positioning = obj(raw["positioning"]);
  const expectedMove = obj(positioning["expected_move"]);
  const pinComponentsRaw = obj(positioning["pin_components"]);
  const hasPinComponents = Object.keys(pinComponentsRaw).length > 0;
  const reversal = obj(positioning["reversal_watch"]);
  const conditionsRaw = reversal["conditions"];
  const flow = obj(raw["flow"]);
  const iv = obj(raw["iv"]);
  const vc = obj(raw["vanna_charm"]);
  const sources = obj(raw["sources"]);
  const nasdaq = obj(sources["nasdaq"]);
  const spot = num(raw["spot"]) ?? num(gamma["spot"]);

  const byStrikeAll = mapStrikes(gamma["by_strike"]);
  // Window the chart to strikes near spot (the far wings are all ~0 GEX and
  // would crush the scale); top strikes carry the full picture in table form.
  const byStrike =
    spot !== null
      ? byStrikeAll.filter((s) => Math.abs(s.strike - spot) <= 14)
      : byStrikeAll.slice(0, 31);

  const bucketsRaw = positioning["hedge_buckets"];
  const hedgeBuckets: LivePayload["hedgeBuckets"] = [];
  if (Array.isArray(bucketsRaw)) {
    for (const b of bucketsRaw) {
      const r = obj(b);
      const bp = num(r["shock_bp"]);
      if (bp === null) continue;
      hedgeBuckets.push({
        shockBp: bp,
        dS: num(r["dS"]),
        notionalM: num(r["notional_m"]),
        direction: str(r["direction"]),
      });
    }
  }

  return {
    status: str(raw["status"]) ?? "unknown",
    updatedAt,
    quoteAsOf: str(raw["quote_as_of"]),
    marketOpen: raw["market_open"] === true,
    spot,
    expiry: str(raw["expiry"]) ?? str(gamma["expiry"]),
    netGexM: num(gamma["net_gex_m"]),
    gammaFlip: num(gamma["gamma_flip"]),
    callWall: num(gamma["call_wall"]),
    putWall: num(gamma["put_wall"]),
    maxPain: num(gamma["max_pain"]),
    regime: str(gamma["regime"]),
    pinScore: num(positioning["pin_score"]),
    pinMagnet: num(positioning["pin_magnet"]),
    pinComponents: hasPinComponents
      ? {
          concentration: num(pinComponentsRaw["concentration"]),
          proximity: num(pinComponentsRaw["proximity"]),
          timeElapsed: num(pinComponentsRaw["time_elapsed"]),
        }
      : null,
    expectedMoveDollars: num(expectedMove["dollars"]),
    expectedMovePct: num(expectedMove["pct"]),
    expectedMoveRemaining: num(expectedMove["remaining_dollars"]),
    hedgeBuckets,
    dealerGammaPerPtM: num(positioning["dealer_gamma_notional_m_per_pt"]),
    speedMPerPt2: num(gamma["speed_m_per_pt2"]),
    speedWideMPerPt2: num(gamma["speed_wide_m_per_pt2"]),
    reversalConditions: Array.isArray(conditionsRaw)
      ? conditionsRaw.filter((c): c is string => typeof c === "string")
      : [],
    reversalStretched:
      typeof reversal["stretched"] === "boolean" ? reversal["stretched"] : null,
    pcVolume: num(flow["pc_volume"]),
    pcOi: num(flow["pc_oi"]),
    callVolume: num(flow["call_volume"]),
    putVolume: num(flow["put_volume"]),
    atmCallIv: num(iv["atm_call_iv"]),
    atmPutIv: num(iv["atm_put_iv"]),
    riskReversal25d: num(iv["risk_reversal_25d"]),
    totalVannaK: num(vc["total_vanna_k"]),
    totalCharmK: num(vc["total_charm_k"]),
    byStrike,
    topStrikes: mapStrikes(gamma["top_strikes"]).slice(0, 6),
    strikeCoverage: strikeCoverage(byStrikeAll),
    elevatedActivity: mapActivity(flow["elevated_volume_activity"]),
    rtdStrikes: num(raw["n_strikes_rtd_live"]),
    nasdaqStrikes: num(raw["n_strikes_nasdaq_delayed"]),
    nasdaqAsOf: str(nasdaq["as_of"]),
    nasdaqStale:
      typeof nasdaq["stale"] === "boolean" ? nasdaq["stale"] : null,
  };
}

async function fetchFeed(): Promise<
  { payload: LivePayload; rawJson: string } | { error: string }
> {
  let lastError = "feed unreachable";
  for (const url of FEED_URLS) {
    try {
      const resp = await fetch(url, {
        headers: { "User-Agent": "muse-0dte-streaming-dashboard/1.0" },
        signal: AbortSignal.timeout(9000),
      });
      if (!resp.ok) {
        lastError = `${url} returned HTTP ${resp.status}`;
        continue;
      }
      const raw = (await resp.json()) as Record<string, unknown>;
      if (str(raw["status"]) !== "ok") {
        lastError = `interpreter status: ${str(raw["status"]) ?? "unknown"}`;
        continue;
      }
      const payload = normalize(raw);
      if (!payload) {
        lastError = "interpreter payload missing updated_at";
        continue;
      }
      return { payload, rawJson: JSON.stringify(raw) };
    } catch (e) {
      lastError = e instanceof Error ? e.message : String(e);
    }
  }
  return { error: lastError };
}

// ---------------------------------------------------------------------------
// Snapshot persistence (throttled, deduped, pruned)
// ---------------------------------------------------------------------------

const MIN_SNAPSHOT_GAP_MS = 45_000;
const MAX_SNAPSHOTS = 1500;

// ADOPT-C1-R1: observation identity is the validated UTC instant
// (snapshots.instant_ms), never the timestamp's textual spelling. The
// same instant spelled with Z or an equivalent numeric offset is ONE
// observation; the first stored row for an instant wins and later
// deliveries of that instant — in any spelling, with any payload — do
// not insert, merge or overwrite (the C05 first-stored-wins behavior,
// generalized from string identity to instant identity). The stored
// `updated_at` string and payload keep the original spelling/bytes.
// Ties between stored rows (legacy same-instant rows only) resolve
// deterministically by row id: the highest id is "newest", trail
// order is (instant, id) ascending. Legacy rows with instant_ms NULL
// (unparseable timestamp) are excluded from latest/trail selection
// and prune first. Admission is atomic at the storage layer: the
// snapshots_unique_instant trigger (migration 0003) ignores an
// insert whose instant is already stored, so overlapping writes of
// one instant cannot both land even when both pass the checks below.
async function maybePersistSnapshot(
  ctx: Ctx,
  payload: LivePayload,
  rawJson: string,
): Promise<void> {
  const db = ctx.db<typeof schema>();
  const instant = parseAwareInstant(payload.updatedAt);
  if (instant === null) return; // unreachable post-normalize; never persist unkeyed
  // Identity: any stored row for this instant dedupes, whatever spelling
  // it was stored under (including pre-migration rows backfilled by 0003).
  const same = await db
    .select({ id: schema.snapshots.id })
    .from(schema.snapshots)
    .where(eq(schema.snapshots.instantMs, instant))
    .limit(1);
  if (same.length > 0) return;
  // Throttle against the latest persisted instant (chronological key).
  const latest = await db
    .select({
      instantMs: schema.snapshots.instantMs,
    })
    .from(schema.snapshots)
    .where(isNotNull(schema.snapshots.instantMs))
    .orderBy(desc(schema.snapshots.instantMs), desc(schema.snapshots.id))
    .limit(1);
  const latestInstant = latest[0]?.instantMs ?? null;
  if (latestInstant !== null) {
    const gap = instant - latestInstant;
    if (gap >= 0 && gap < MIN_SNAPSHOT_GAP_MS) return;
  }
  try {
    await db.insert(schema.snapshots).values({
      updatedAt: payload.updatedAt,
      instantMs: instant,
      spot: payload.spot,
      maxPain: payload.maxPain,
      callWall: payload.callWall,
      putWall: payload.putWall,
      gammaFlip: payload.gammaFlip,
      netGexM: payload.netGexM,
      pinScore: payload.pinScore,
      expectedMove: payload.expectedMoveRemaining,
      regime: payload.regime,
      payloadJson: rawJson,
    });
  } catch {
    // Unique-constraint race with a concurrent poll — the row exists, fine.
    return;
  }
  // Prune to exactly the newest MAX_SNAPSHOTS observations by
  // (instant, id); arrival order no longer decides what survives, so a
  // late-arriving old frame can never evict a newer accepted one — at
  // capacity it is the row pruned.
  const ordered = await db
    .select({
      id: schema.snapshots.id,
      instantMs: schema.snapshots.instantMs,
    })
    .from(schema.snapshots)
    .orderBy(desc(schema.snapshots.instantMs), desc(schema.snapshots.id));
  if (ordered.length > MAX_SNAPSHOTS) {
    const boundary = ordered[MAX_SNAPSHOTS - 1];
    if (boundary) {
      // Delete exactly the rows ordered below the boundary row. NULL
      // instants sort below every real instant, so against a real
      // boundary they all go; against a NULL boundary (more legacy
      // NULL rows than the excess) only the lower-id NULL tail goes.
      const below =
        boundary.instantMs === null
          ? and(
              isNull(schema.snapshots.instantMs),
              lt(schema.snapshots.id, boundary.id),
            )
          : or(
              isNull(schema.snapshots.instantMs),
              lt(schema.snapshots.instantMs, boundary.instantMs),
              and(
                eq(schema.snapshots.instantMs, boundary.instantMs),
                lt(schema.snapshots.id, boundary.id),
              ),
            );
      await db.delete(schema.snapshots).where(below);
    }
  }
}

async function loadTrailAndLatest(
  ctx: Ctx,
): Promise<{
  trail: z.infer<typeof trailPoint>[];
  staleSnapshot: LivePayload | null;
  staleSnapshotAt: string | null;
}> {
  const db = ctx.db<typeof schema>();
  const rows = await db
    .select({
      updatedAt: schema.snapshots.updatedAt,
      spot: schema.snapshots.spot,
      callWall: schema.snapshots.callWall,
      putWall: schema.snapshots.putWall,
      gammaFlip: schema.snapshots.gammaFlip,
      maxPain: schema.snapshots.maxPain,
      pinScore: schema.snapshots.pinScore,
      netGexM: schema.snapshots.netGexM,
    })
    .from(schema.snapshots)
    // Chronological key (ADOPT-C1-R1): newest 240 by (instant, id),
    // reversed below into ascending instant order for the trail.
    // Unkeyed rows (instant_ms NULL — inadmissible legacy clocks) are
    // EXCLUDED from accepted observations, never merely sorted last:
    // unkeyed-only storage yields an empty trail and no fallback.
    .where(isNotNull(schema.snapshots.instantMs))
    .orderBy(desc(schema.snapshots.instantMs), desc(schema.snapshots.id))
    .limit(240);
  const trail = rows
    .map((r) => ({
      updatedAt: r.updatedAt,
      spot: r.spot,
      callWall: r.callWall,
      putWall: r.putWall,
      gammaFlip: r.gammaFlip,
      maxPain: r.maxPain,
      pinScore: r.pinScore,
      netGexM: r.netGexM,
    }))
    .reverse();

  const newest = await db
    .select({
      updatedAt: schema.snapshots.updatedAt,
      payloadJson: schema.snapshots.payloadJson,
    })
    .from(schema.snapshots)
    // Newest = greatest validated instant; ties (legacy same-instant
    // rows) resolve to the highest id, deterministically. Unkeyed
    // rows are excluded (see the trail query above).
    .where(isNotNull(schema.snapshots.instantMs))
    .orderBy(desc(schema.snapshots.instantMs), desc(schema.snapshots.id))
    .limit(1);
  let staleSnapshot: LivePayload | null = null;
  let staleSnapshotAt: string | null = null;
  const newestRow = newest[0];
  if (newestRow) {
    staleSnapshotAt = newestRow.updatedAt;
    try {
      const parsed = JSON.parse(newestRow.payloadJson) as Record<
        string,
        unknown
      >;
      staleSnapshot = normalize(parsed);
    } catch {
      staleSnapshot = null;
    }
  }
  return { trail, staleSnapshot, staleSnapshotAt };
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export const Actions = {
  /**
   * One live read: fetch the interpreter, persist a throttled snapshot,
   * and return the normalized payload plus the persisted intraday trail.
   * The client polls this every 15s while the page is open — that polling
   * IS the stream for this runtime; the page updates in place with no
   * rebuild or republish.
   */
  getLive: defineAction({
    request: z.object({}),
    response: getLiveResponse,
    async handler(ctx): Promise<GetLiveResponse> {
      const fetchedAt = new Date().toISOString();
      const result = await fetchFeed();
      if ("error" in result) {
        const { trail, staleSnapshot, staleSnapshotAt } =
          await loadTrailAndLatest(ctx);
        return {
          ok: false,
          feedError: result.error,
          fetchedAt,
          live: null,
          staleSnapshot,
          staleSnapshotAt,
          trail,
        };
      }
      await maybePersistSnapshot(ctx, result.payload, result.rawJson);
      const { trail } = await loadTrailAndLatest(ctx);
      return {
        ok: true,
        feedError: null,
        fetchedAt,
        live: result.payload,
        staleSnapshot: null,
        staleSnapshotAt: null,
        trail,
      };
    },
  }),

  /**
   * The signal layer from /feed/signals, fetched on the same 15s client
   * poll as getLive. Fully independent of the main feed: any failure,
   * non-"ok" status, or malformed payload returns { ok: false,
   * signals: null } and the panel shows a muted "signals unavailable"
   * note — the rest of the page is unaffected.
   */
  getSignals: defineAction({
    request: z.object({}),
    response: getSignalsResponse,
    async handler(): Promise<GetSignalsResponse> {
      const signals = await fetchSignals();
      return { ok: signals !== null, signals };
    },
  }),
} satisfies ActionsModule;
