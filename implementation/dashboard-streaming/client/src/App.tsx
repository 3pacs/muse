import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { SafeAreaTopScrim } from "@hatch/space-sdk/client";
import {
Bar,
BarChart,
CartesianGrid,
Cell,
Line,
LineChart,
ReferenceLine,
ResponsiveContainer,
Tooltip,
XAxis,
YAxis,
} from "recharts";
import { api, type ApiResponse } from "./api";

type Live = NonNullable<ApiResponse<typeof api, "getLive">["live"]>;
type TrailPoint = ApiResponse<typeof api, "getLive">["trail"][number];
type Signals = NonNullable<ApiResponse<typeof api, "getSignals">["signals"]>;

const PT = "America/Los_Angeles";
const POLL_MS = 15_000;

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString("en-US");
}

function fmtMoneyM(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  const sign = n < 0 ? "−" : "";
  return `${sign}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}M`;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: PT,
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(d);
}

function fmtTimeShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: PT,
    hour: "numeric",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

function ageLabel(iso: string | null | undefined, nowMs: number): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const secs = Math.max(0, Math.round((nowMs - t) / 1000));
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

// ---------------------------------------------------------------------------
// Level ladder — the hero. One horizontal price axis; every level the trader
// cares about placed on it, with the expected-move band shaded around spot.
// ---------------------------------------------------------------------------

function LevelLadder({ live }: { live: Live }) {
  const spot = live.spot;
  const em = live.expectedMoveRemaining ?? live.expectedMoveDollars;
  const levels = useMemo(() => {
    const pts: { value: number; kind: string }[] = [];
    if (live.putWall !== null) pts.push({ value: live.putWall, kind: "put" });
    if (live.callWall !== null)
      pts.push({ value: live.callWall, kind: "call" });
    if (live.gammaFlip !== null)
      pts.push({ value: live.gammaFlip, kind: "flip" });
    if (live.maxPain !== null) pts.push({ value: live.maxPain, kind: "pain" });
    if (spot !== null) pts.push({ value: spot, kind: "spot" });
    if (spot !== null && em !== null) {
      pts.push({ value: spot - em, kind: "band" });
      pts.push({ value: spot + em, kind: "band" });
    }
    return pts;
  }, [live, spot, em]);

  if (spot === null || levels.length === 0) return null;

  const rawMin = Math.min(...levels.map((l) => l.value));
  const rawMax = Math.max(...levels.map((l) => l.value));
  const pad = Math.max(1, (rawMax - rawMin) * 0.12);
  const min = Math.floor((rawMin - pad) * 2) / 2;
  const max = Math.ceil((rawMax + pad) * 2) / 2;
  const pos = (v: number) => ((v - min) / (max - min)) * 100;

  type Marker = {
    key: string;
    label: string;
    value: number | null;
    color: string;
    lane: "above" | "below";
    bold?: boolean;
  };
  const markers: Marker[] = [
    {
      key: "call",
      label: "CALL WALL",
      value: live.callWall,
      color: "var(--call)",
      lane: "above",
    },
    {
      key: "spot",
      label: "SPOT",
      value: spot,
      color: "var(--amber-bright)",
      lane: "above",
      bold: true,
    },
    {
      key: "flip",
      label: "FLIP",
      value: live.gammaFlip,
      color: "var(--flip)",
      lane: "below",
    },
    {
      key: "pain",
      label: "MAX PAIN",
      value: live.maxPain,
      color: "var(--dim)",
      lane: "below",
    },
    {
      key: "put",
      label: "PUT WALL",
      value: live.putWall,
      color: "var(--put)",
      lane: "below",
    },
  ];

  // Collision handling: levels cluster tightly exactly when pinning matters
  // (spot, flip, both walls within ~2pts), so labels that would overlap are
  // stacked onto extra rows away from the track instead of colliding.
  const ROW_H = 17;
  const MIN_SEP_PCT = 27;
  function layoutLane(lane: "above" | "below"): { m: Marker; x: number }[][] {
    const items = markers
      .filter((m) => m.lane === lane && m.value !== null)
      .map((m) => ({ m, x: pos(m.value as number) }))
      .sort((a, b) => a.x - b.x);
    const rows: { m: Marker; x: number }[][] = [];
    for (const item of items) {
      let placed = false;
      for (const row of rows) {
        const last = row[row.length - 1];
        if (!last || item.x - last.x >= MIN_SEP_PCT) {
          row.push(item);
          placed = true;
          break;
        }
      }
      if (!placed) rows.push([item]);
    }
    return rows; // rows[0] sits closest to the track
  }
  const aboveRows = layoutLane("above");
  const belowRows = layoutLane("below");
  const clampLabelX = (x: number) => Math.min(90, Math.max(10, x));

  function renderLabel(item: { m: Marker; x: number }) {
    const { m } = item;
    return (
      <div
        key={m.key}
        className="absolute -translate-x-1/2 font-mono text-[11px] leading-tight whitespace-nowrap"
        style={{
          left: `${clampLabelX(item.x)}%`,
          color: m.color,
          fontWeight: m.bold ? 700 : 600,
        }}
      >
        {m.label}{" "}
        {fmt(m.value, m.key === "spot" || m.key === "flip" ? 2 : 0)}
      </div>
    );
  }

  return (
    <div
      className="relative mt-6 select-none"
      role="img"
      aria-label={`Level ladder from ${fmt(min, 1)} to ${fmt(max, 1)}: spot ${fmt(spot)}, call wall ${fmt(live.callWall, 0)}, put wall ${fmt(live.putWall, 0)}, gamma flip ${fmt(live.gammaFlip)}, max pain ${fmt(live.maxPain, 0)}`}
    >
      {/* above-lane labels: farthest row rendered first (on top) */}
      <div
        className="relative"
        style={{ height: Math.max(1, aboveRows.length) * ROW_H }}
      >
        {aboveRows.map((row, ri) =>
          row.map((item) => (
            <div
              key={item.m.key}
              className="absolute right-0 left-0"
              style={{
                top: (aboveRows.length - 1 - ri) * ROW_H,
                height: ROW_H,
              }}
            >
              <div className="relative h-full">{renderLabel(item)}</div>
            </div>
          )),
        )}
      </div>
      {/* track */}
      <div className="relative h-6">
        {spot !== null && em !== null && (
          <div
            className="absolute top-1/2 h-3 -translate-y-1/2 rounded-sm opacity-25"
            style={{
              left: `${pos(spot - em)}%`,
              width: `${pos(spot + em) - pos(spot - em)}%`,
              backgroundColor: "var(--amber)",
            }}
          />
        )}
        <div className="absolute top-1/2 right-0 left-0 h-px -translate-y-1/2 bg-[var(--border)]" />
        {markers
          .filter((m) => m.value !== null)
          .map((m) => (
            <div
              key={m.key}
              className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${pos(m.value as number)}%` }}
            >
              {m.key === "spot" ? (
                <div
                  className="h-3.5 w-3.5 rotate-45 border-2"
                  style={{
                    backgroundColor: "var(--bg)",
                    borderColor: m.color,
                  }}
                />
              ) : (
                <div
                  className="h-4 w-[3px] rounded-full"
                  style={{ backgroundColor: m.color }}
                />
              )}
            </div>
          ))}
      </div>
      {/* below-lane labels: closest row first */}
      <div
        className="relative"
        style={{ height: Math.max(1, belowRows.length) * ROW_H }}
      >
        {belowRows.map((row, ri) =>
          row.map((item) => (
            <div
              key={item.m.key}
              className="absolute right-0 left-0"
              style={{ top: ri * ROW_H, height: ROW_H }}
            >
              <div className="relative h-full">{renderLabel(item)}</div>
            </div>
          )),
        )}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--dim)]">
        <span>{fmt(min, 1)}</span>
        <span>shaded band = expected move ±{fmt(em)}</span>
        <span>{fmt(max, 1)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

function Stat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-semibold tracking-wide text-[var(--dim)] uppercase">
        {label}
      </div>
      <div
        className="font-mono text-lg leading-snug font-semibold break-words"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
      {sub && <div className="font-mono text-[11px] text-[var(--dim)]">{sub}</div>}
    </div>
  );
}

function Panel({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-md border border-[var(--border)] bg-[var(--surface)] p-4 ${className}`}
    >
      <h2 className="mb-3 text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

const tooltipStyle = {
  backgroundColor: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  color: "var(--text)",
  fontFamily: "var(--font-mono)",
  fontSize: 12,
} as const;

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function GexChart({ live }: { live: Live }) {
  const data = live.byStrike.map((s) => ({
    strike: s.strike,
    net: s.netGexM,
  }));
  if (data.length === 0) {
    return <p className="text-sm text-[var(--dim)]">No strike data in this snapshot.</p>;
  }
  return (
    <div className="h-56 w-full" aria-label="Net GEX by strike chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="strike"
            tick={{ fill: "var(--dim)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--dim)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={(v: number) => `$${v}`}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: unknown) => [`$${fmt(numOrNull(v), 1)}M`, "Net GEX"]}
            labelFormatter={(l: unknown) => `Strike ${l}`}
          />
          <ReferenceLine y={0} stroke="var(--dim)" />
          <Bar dataKey="net" radius={[2, 2, 0, 0]}>
            {data.map((d) => (
              <Cell
                key={d.strike}
                fill={d.net >= 0 ? "var(--gamma-pos)" : "var(--gamma-neg)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function numOrNull(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function TrailChart({ trail }: { trail: TrailPoint[] }) {
  const data = trail.map((p) => ({
    t: fmtTimeShort(p.updatedAt),
    spot: p.spot,
    callWall: p.callWall,
    putWall: p.putWall,
    flip: p.gammaFlip,
    maxPain: p.maxPain,
  }));
  if (data.length < 2) {
    return (
      <p className="text-sm text-[var(--dim)]">
        The trail builds as snapshots accumulate while this page is open — one
        point per minute, kept for the last three trading days.
      </p>
    );
  }
  const lineProps = {
    dot: false,
    strokeWidth: 1.5,
    connectNulls: true,
    isAnimationActive: false,
  } as const;
  return (
    <div className="h-52 w-full" aria-label="Intraday trail: spot versus walls, flip and max pain">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fill: "var(--dim)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fill: "var(--dim)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v: number) => fmt(v, 0)}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: unknown, name: unknown) => [fmt(numOrNull(v)), String(name)]}
          />
          <Line type="stepAfter" dataKey="callWall" name="Call wall" stroke="var(--call)" {...lineProps} />
          <Line type="stepAfter" dataKey="putWall" name="Put wall" stroke="var(--put)" {...lineProps} />
          <Line type="stepAfter" dataKey="flip" name="Flip" stroke="var(--flip)" {...lineProps} strokeDasharray="4 3" />
          <Line type="stepAfter" dataKey="maxPain" name="Max pain" stroke="var(--dim)" {...lineProps} strokeDasharray="2 3" />
          <Line type="monotone" dataKey="spot" name="Spot" stroke="var(--amber-bright)" {...lineProps} strokeWidth={2.25} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signals panel — the interpreter's signal layer (/feed/signals): loaded-gun
// state, last charm trigger, indicator stacks, extremes & share prints.
// Fetched on the same 15s poll as the main feed; when unavailable the panel
// degrades to a muted note and nothing else on the page is affected.
// ---------------------------------------------------------------------------

function fmtEtTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const m = ts.match(/(\d{1,2}:\d{2})/);
  return m?.[1] ?? ts;
}

function DirMark({ direction }: { direction: string | null }) {
  if (direction === "bull") {
    return (
      <span style={{ color: "var(--gamma-pos)" }} aria-label="bullish">
        ▲
      </span>
    );
  }
  if (direction === "bear") {
    return (
      <span style={{ color: "var(--put)" }} aria-label="bearish">
        ▼
      </span>
    );
  }
  return <span className="text-[var(--dim)]">•</span>;
}

function SignalsPanel({
  signals,
  speed,
  speedWide,
}: {
  signals: Signals | null;
  speed: number | null;
  speedWide: number | null;
}) {
  return (
    <section className="mt-3 rounded-md border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
          Signals
        </h2>
        <span className="font-mono text-[11px] text-[var(--dim)]">
          Speed: {fmt(speed, 1)} / wide {fmt(speedWide, 1)} $M/pt²
        </span>
      </div>

      {signals === null ? (
        <p className="font-mono text-xs text-[var(--dim)]">
          Signals unavailable — the interpreter's /feed/signals did not
          answer. The rest of this page is unaffected.
        </p>
      ) : (
        <>
          {/* Loaded-gun state banner */}
          {signals.loadedGun.active ? (
            <div
              className="rounded-md border px-3 py-2.5"
              style={{
                borderColor: "var(--put)",
                backgroundColor: "var(--surface-alt)",
              }}
              role="alert"
            >
              <div
                className="font-mono text-base font-bold"
                style={{ color: "var(--put)" }}
              >
                🔫 LOADED GUN
              </div>
              <div className="mt-1 font-mono text-xs">
                since {signals.loadedGun.sinceEt ?? "—"} ET · spot{" "}
                {fmt(signals.loadedGun.spot)} · pin{" "}
                {signals.loadedGun.pin !== null
                  ? fmt(signals.loadedGun.pin, 0)
                  : "—"}{" "}
                · net GEX {fmtMoneyM(signals.loadedGun.netGexM)} · budget left{" "}
                {signals.loadedGun.budgetLeft !== null
                  ? `${fmt(signals.loadedGun.budgetLeft * 100, 0)}%`
                  : "—"}
                {signals.loadedGun.flipDist !== null
                  ? ` · flip dist ${fmt(signals.loadedGun.flipDist)}`
                  : ""}
              </div>
            </div>
          ) : (
            <p className="font-mono text-xs text-[var(--dim)]">
              Loaded gun: off
            </p>
          )}

          {signals.lastCharmTrigger && (
            <p className="mt-2 font-mono text-xs">
              🎯 Last charm trigger {signals.lastCharmTrigger.tsEt ?? "—"} ET
              — SPY {fmt(signals.lastCharmTrigger.spot)}, charm velocity{" "}
              {fmtInt(signals.lastCharmTrigger.charmVel30)}
            </p>
          )}

          {/* Stacks */}
          <h3 className="mt-5 mb-2 text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
            Stacks
          </h3>
          {signals.stacks.length === 0 ? (
            <p className="text-sm text-[var(--dim)]">No stacks yet today.</p>
          ) : (
            <ul className="space-y-2 font-mono text-xs">
              {signals.stacks.map((s, i) => (
                <li
                  key={`${s.tsEt}-${s.symbol}-${i}`}
                  className="border-b border-[var(--border)] pb-2 last:border-0"
                >
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-[var(--dim)]">
                      {fmtEtTime(s.tsEt)} ET
                    </span>
                    <span className="font-bold">{s.symbol}</span>
                    <DirMark direction={s.direction} />
                    <span>{fmt(s.spot)}</span>
                    {s.path && (
                      <span className="text-[var(--dim)]">path {s.path}</span>
                    )}
                  </div>
                  {s.members.length > 0 && (
                    <div className="mt-0.5 text-[var(--dim)]">
                      {s.members.join(" + ")}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Extremes & prints */}
          <h3 className="mt-5 mb-2 text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
            Extremes &amp; prints
          </h3>
          {signals.extremes.length === 0 ? (
            <p className="text-sm text-[var(--dim)]">
              No extremes flagged yet today.
            </p>
          ) : (
            <ul className="space-y-2 font-mono text-xs">
              {signals.extremes.map((e, i) => {
                if (e.type === "vol_ignition") {
                  return (
                    <li
                      key={`${e.tsEt}-${e.symbol}-${e.type}-${i}`}
                      className="rounded-sm border border-[var(--border)] bg-[var(--surface-alt)] px-2.5 py-2"
                    >
                      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                        <span aria-hidden="true">🖨️</span>
                        <span className="text-[var(--dim)]">
                          {fmtEtTime(e.tsEt)} ET
                        </span>
                        <span className="font-bold">{e.symbol}</span>
                        <DirMark direction={e.direction} />
                        <span>{fmt(e.spot)}</span>
                        <span className="font-bold">
                          {fmtInt(e.vol)} shares
                        </span>
                        {e.mult !== null && (
                          <span>{fmt(e.mult, 1)}× median</span>
                        )}
                        {e.mega === true && (
                          <span
                            className="rounded-sm px-1.5 py-0.5 text-[10px] font-bold"
                            style={{
                              color: "var(--amber-bright)",
                              border: "1px solid var(--amber)",
                            }}
                          >
                            MEGA
                          </span>
                        )}
                        {e.atLows === true && <span>at lows</span>}
                        {e.atHighs === true && <span>at highs</span>}
                      </div>
                      <div className="mt-1">
                        {e.cluster === true ? (
                          <span style={{ color: "var(--amber)" }}>
                            ⚠️ CLUSTERING ({fmtInt(e.prints60m)} in last hour)
                          </span>
                        ) : (
                          <span className="text-[var(--dim)]">isolated</span>
                        )}
                      </div>
                    </li>
                  );
                }
                return (
                  <li
                    key={`${e.tsEt}-${e.symbol}-${e.type}-${i}`}
                    className="flex flex-wrap items-baseline gap-x-2 border-b border-[var(--border)] pb-1.5 last:border-0"
                  >
                    <span className="text-[var(--dim)]">
                      {fmtEtTime(e.tsEt)} ET
                    </span>
                    <span className="font-bold">{e.symbol}</span>
                    <span>{e.type}</span>
                    <DirMark direction={e.direction} />
                    <span>{fmt(e.spot)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------

type ConnStatus = "live" | "stale" | "down" | "closed" | "paused";

export function App() {
  const [paused, setPaused] = useState(false);
  const query = useQuery({
    queryKey: ["live-feed"],
    queryFn: () => api.getLive({}),
    refetchInterval: paused ? false : POLL_MS,
    refetchOnWindowFocus: true,
  });

  const signalsQuery = useQuery({
    queryKey: ["signals-feed"],
    queryFn: () => api.getSignals({}),
    refetchInterval: paused ? false : POLL_MS,
    refetchOnWindowFocus: true,
  });
  const signals = signalsQuery.data?.signals ?? null;

  const data = query.data;
  const live = data?.live ?? null;
  const display: Live | null = live ?? data?.staleSnapshot ?? null;
  const showingStale = live === null && display !== null;
  const nowMs = Date.now();
  const ageMs = display ? nowMs - new Date(display.updatedAt).getTime() : null;

  const status: ConnStatus = paused
    ? "paused"
    : !data || query.isError
      ? "down"
      : showingStale || !data.ok
        ? "down"
        : display && !display.marketOpen
          ? "closed"
          : ageMs !== null && ageMs > 120_000
            ? "stale"
            : "live";

  const statusMeta: Record<
    ConnStatus,
    { label: string; color: string; pulse: boolean }
  > = {
    live: { label: "LIVE", color: "var(--gamma-pos)", pulse: true },
    stale: { label: "STALE", color: "var(--amber)", pulse: false },
    down: { label: "FEED DOWN", color: "var(--put)", pulse: false },
    closed: { label: "MARKET CLOSED", color: "var(--dim)", pulse: false },
    paused: { label: "PAUSED", color: "var(--dim)", pulse: false },
  };
  const sm = statusMeta[status];

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <SafeAreaTopScrim backgroundColor="var(--bg)" />
      <main className="mx-auto w-full max-w-5xl px-3 pb-10 sm:px-5">
        {/* Status + controls bar */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-4">
          <span
            className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 font-mono text-xs font-bold"
            role="status"
            aria-label={`Feed status: ${sm.label}`}
          >
            <span
              className={`h-2 w-2 rounded-full ${sm.pulse ? "live-dot" : ""}`}
              style={{ backgroundColor: sm.color }}
            />
            <span style={{ color: sm.color }}>{sm.label}</span>
          </span>
          <span className="font-mono text-xs text-[var(--dim)]">
            SPY · 0DTE{display?.expiry ? ` · exp ${display.expiry}` : ""}
            {display
              ? ` · updated ${fmtTime(display.updatedAt)} PT (${ageLabel(display.updatedAt, nowMs)})`
              : ""}
          </span>
          <span className="ml-auto flex gap-2">
            <button
              type="button"
              aria-label={paused ? "Resume live updates" : "Pause live updates"}
              onClick={() => setPaused((p) => !p)}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 font-mono text-xs font-semibold"
            >
              {paused ? "Resume" : "Pause"}
            </button>
            <button
              type="button"
              aria-label="Refresh now"
              onClick={() => void query.refetch()}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 font-mono text-xs font-semibold"
            >
              {query.isFetching ? "Refreshing…" : "Refresh"}
            </button>
          </span>
        </div>

        {/* Banners */}
        {showingStale && (
          <div
            className="mt-3 rounded-md border px-3 py-2 font-mono text-xs"
            style={{ borderColor: "var(--put)", color: "var(--put)" }}
            role="alert"
          >
            Interpreter feed unreachable
            {data?.feedError ? ` (${data.feedError})` : ""} — showing the last
            snapshot this page stored, from {fmtTime(display?.updatedAt)} PT.
            Nothing below is live.
          </div>
        )}
        {status === "closed" && !showingStale && (
          <div className="mt-3 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-mono text-xs text-[var(--dim)]">
            Market closed — showing the latest interpreter snapshot. Levels
            update again at the next session.
          </div>
        )}

        {/* Loading / hard-empty states */}
        {query.isPending && (
          <p className="py-16 text-center font-mono text-sm text-[var(--dim)]">
            Connecting to the interpreter feed…
          </p>
        )}
        {!query.isPending && !display && (
          <div className="py-16 text-center">
            <p className="font-mono text-base font-semibold">No snapshot yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-[var(--dim)]">
              The interpreter at :8787 did not answer
              {data?.feedError ? ` — ${data.feedError}` : ""}, and this page has
              no stored snapshot to fall back on. Snapshots accumulate here
              while the page is open during market hours.
            </p>
            <button
              type="button"
              aria-label="Retry feed connection"
              onClick={() => void query.refetch()}
              className="mt-4 rounded-md border border-[var(--border)] bg-[var(--surface)] px-4 py-2 font-mono text-sm font-semibold"
            >
              Retry
            </button>
          </div>
        )}

        {display && (
          <>
            {/* Hero: spot + ladder */}
            <section className="mt-4 rounded-md border border-[var(--border)] bg-[var(--surface)] px-4 pt-4 pb-3">
              <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
                <div>
                  <div className="text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
                    SPY spot
                  </div>
                  <div className="font-mono text-5xl leading-none font-bold tracking-tight">
                    {fmt(display.spot)}
                  </div>
                </div>
                <div className="pb-1">
                  <span
                    className="inline-block rounded-sm px-2 py-0.5 font-mono text-xs font-bold"
                    style={{
                      color:
                        display.netGexM !== null && display.netGexM >= 0
                          ? "var(--gamma-pos)"
                          : "var(--gamma-neg)",
                      border: `1px solid ${
                        display.netGexM !== null && display.netGexM >= 0
                          ? "var(--gamma-pos)"
                          : "var(--gamma-neg)"
                      }`,
                    }}
                  >
                    {display.regime ?? "regime —"}
                  </span>
                  <div className="mt-1.5 font-mono text-xs text-[var(--dim)]">
                    Net GEX {fmtMoneyM(display.netGexM)} per 1% · flip{" "}
                    {fmt(display.gammaFlip)} · quote as of{" "}
                    {fmtTime(display.quoteAsOf)} PT
                  </div>
                </div>
              </div>
              <LevelLadder live={display} />
            </section>

            {/* Signals */}
            <SignalsPanel
              signals={signals}
              speed={display.speedMPerPt2}
              speedWide={display.speedWideMPerPt2}
            />

            {/* GEX + positioning */}
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <Panel title="Net GEX by strike ($M per 1% move)">
                <GexChart live={display} />
                <p className="mt-2 font-mono text-[11px] text-[var(--dim)]">
                  Windowed to spot ±14. Green = positive gamma strike, red =
                  negative. Walls and flip are computed over the full chain.
                </p>
              </Panel>

              <Panel title="Pin & dealer positioning">
                <div className="flex items-end gap-3">
                  <div className="font-mono text-4xl font-bold">
                    {display.pinScore !== null
                      ? fmt(display.pinScore, 0)
                      : "—"}
                  </div>
                  <div className="pb-1 font-mono text-xs text-[var(--dim)]">
                    pin score / 100
                    {display.pinMagnet !== null
                      ? ` · magnet ${fmt(display.pinMagnet, 0)}`
                      : ""}
                  </div>
                </div>
                <div
                  className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-[var(--surface-alt)]"
                  role="img"
                  aria-label={`Pin score ${display.pinScore !== null ? fmt(display.pinScore, 0) : "unavailable"} out of 100`}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.max(0, Math.min(100, display.pinScore ?? 0))}%`,
                      backgroundColor: "var(--amber)",
                    }}
                  />
                </div>
                {display.pinComponents && (
                  <div className="mt-3 grid grid-cols-3 gap-3 font-mono text-[11px] text-[var(--dim)]">
                    <span>
                      concentration{" "}
                      <span className="text-[var(--text)]">
                        {display.pinComponents.concentration !== null
                          ? fmt(display.pinComponents.concentration * 100, 0) + "%"
                          : "—"}
                      </span>
                    </span>
                    <span>
                      proximity{" "}
                      <span className="text-[var(--text)]">
                        {display.pinComponents.proximity !== null
                          ? fmt(display.pinComponents.proximity * 100, 0) + "%"
                          : "—"}
                      </span>
                    </span>
                    <span>
                      session elapsed{" "}
                      <span className="text-[var(--text)]">
                        {display.pinComponents.timeElapsed !== null
                          ? fmt(display.pinComponents.timeElapsed * 100, 0) + "%"
                          : "—"}
                      </span>
                    </span>
                  </div>
                )}

                <h3 className="mt-5 mb-2 text-[11px] font-bold tracking-[0.14em] text-[var(--dim)] uppercase">
                  Dealer re-hedge per spot shock
                </h3>
                {display.hedgeBuckets.length === 0 ? (
                  <p className="text-sm text-[var(--dim)]">Unavailable in this snapshot.</p>
                ) : (
                  <div className="space-y-1.5">
                    {display.hedgeBuckets.map((b) => {
                      const maxAbs = Math.max(
                        ...display.hedgeBuckets.map((x) =>
                          Math.abs(x.notionalM ?? 0),
                        ),
                        1,
                      );
                      const w =
                        (Math.abs(b.notionalM ?? 0) / maxAbs) * 100;
                      const sell = (b.notionalM ?? 0) < 0;
                      return (
                        <div
                          key={b.shockBp}
                          className="flex items-center gap-2 font-mono text-xs"
                        >
                          <span className="w-14 shrink-0 text-[var(--dim)]">
                            ±{b.shockBp}bp
                          </span>
                          <div className="h-3.5 flex-1 overflow-hidden rounded-sm bg-[var(--surface-alt)]">
                            <div
                              className="h-full"
                              style={{
                                width: `${w}%`,
                                backgroundColor: sell
                                  ? "var(--put)"
                                  : "var(--gamma-pos)",
                              }}
                            />
                          </div>
                          <span className="w-24 shrink-0 text-right">
                            {fmtMoneyM(b.notionalM)}{" "}
                            <span className="text-[var(--dim)]">
                              {b.direction ?? ""}
                            </span>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                {display.reversalConditions.length > 0 && (
                  <div className="mt-4 border-t border-[var(--border)] pt-3">
                    {display.reversalConditions.map((c) => (
                      <p key={c} className="font-mono text-xs text-[var(--amber)]">
                        ⚠ {c}
                      </p>
                    ))}
                  </div>
                )}
              </Panel>
            </div>

            {/* Trail */}
            <Panel title="Today's trail — spot vs levels (PT)" className="mt-3">
              <TrailChart trail={data?.trail ?? []} />
            </Panel>

            {/* Flow / IV / strikes */}
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              <Panel title="Flow & IV">
                <div className="grid grid-cols-2 gap-x-4 gap-y-4">
                  <Stat
                    label="Expected move"
                    value={
                      display.expectedMoveRemaining !== null
                        ? `±${fmt(display.expectedMoveRemaining)}`
                        : "—"
                    }
                    sub={
                      display.expectedMovePct !== null
                        ? `${fmt(display.expectedMovePct, 3)}% to expiry`
                        : undefined
                    }
                  />
                  <Stat
                    label="P/C volume"
                    value={fmt(display.pcVolume)}
                    sub={`calls ${fmtInt(display.callVolume)} · puts ${fmtInt(display.putVolume)}`}
                  />
                  <Stat label="P/C open interest" value={fmt(display.pcOi)} />
                  <Stat
                    label="ATM IV"
                    value={
                      display.atmCallIv !== null || display.atmPutIv !== null
                        ? `${display.atmCallIv !== null ? fmt(display.atmCallIv * 100, 1) + "%" : "—"} / ${display.atmPutIv !== null ? fmt(display.atmPutIv * 100, 1) + "%" : "—"}`
                        : "—"
                    }
                    sub="call / put"
                  />
                  <Stat
                    label="25Δ risk reversal"
                    value={
                      display.riskReversal25d !== null
                        ? fmt(display.riskReversal25d * 100, 2) + " vol pts"
                        : "unavailable"
                    }
                    sub="feed reports null — not estimated"
                  />
                  <Stat
                    label="Dealer γ / pt"
                    value={fmtMoneyM(display.dealerGammaPerPtM)}
                    sub="per 1pt spot move"
                  />
                  <Stat
                    label="Vanna (total)"
                    value={
                      display.totalVannaK !== null
                        ? `${fmtInt(display.totalVannaK)}k`
                        : "—"
                    }
                  />
                  <Stat
                    label="Charm (total)"
                    value={
                      display.totalCharmK !== null
                        ? `${fmtInt(display.totalCharmK)}k`
                        : "—"
                    }
                  />
                </div>
              </Panel>

              <Panel title="Top strikes by |GEX|">
                {display.topStrikes.length === 0 ? (
                  <p className="text-sm text-[var(--dim)]">Unavailable in this snapshot.</p>
                ) : (
                  <table className="w-full font-mono text-xs">
                    <thead>
                      <tr className="text-left text-[var(--dim)]">
                        <th className="pb-1.5 font-semibold">Strike</th>
                        <th className="pb-1.5 text-right font-semibold">Net</th>
                        <th className="pb-1.5 text-right font-semibold">Call</th>
                        <th className="pb-1.5 text-right font-semibold">Put</th>
                      </tr>
                    </thead>
                    <tbody>
                      {display.topStrikes.map((s) => (
                        <tr key={s.strike} className="border-t border-[var(--border)]">
                          <td className="py-1.5 font-bold">{fmt(s.strike, 0)}</td>
                          <td
                            className="py-1.5 text-right"
                            style={{
                              color:
                                s.netGexM >= 0
                                  ? "var(--gamma-pos)"
                                  : "var(--gamma-neg)",
                            }}
                          >
                            {fmt(s.netGexM, 0)}
                          </td>
                          <td className="py-1.5 text-right">{fmt(s.callGexM, 0)}</td>
                          <td className="py-1.5 text-right">{fmt(s.putGexM, 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="mt-2 font-mono text-[11px] text-[var(--dim)]">$M per 1% spot move</p>
              </Panel>

              <Panel title="Elevated volume activity">
                {display.elevatedActivity.length === 0 ? (
                  <p className="text-sm text-[var(--dim)]">None flagged in this snapshot.</p>
                ) : (
                  <ul className="space-y-2 font-mono text-xs">
                    {display.elevatedActivity.slice(0, 6).map((a, i) => (
                      <li
                        key={`${a.strike}-${a.side}-${i}`}
                        className="flex items-baseline justify-between gap-2 border-b border-[var(--border)] pb-1.5 last:border-0"
                      >
                        <span>
                          <span className="font-bold">{fmt(a.strike, 0)}</span>{" "}
                          <span
                            style={{
                              color:
                                a.side === "put"
                                  ? "var(--put)"
                                  : "var(--call)",
                            }}
                          >
                            {a.side}
                          </span>
                        </span>
                        <span className="text-[var(--dim)]">
                          vol/OI {fmt(a.volOi, 1)} ·{" "}
                          {a.notionalK !== null
                            ? `$${fmtInt(a.notionalK)}k`
                            : "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 font-mono text-[11px] text-[var(--dim)]">
                  Unsigned activity (no trade signing in feed) — volume
                  outliers, not directional flow.
                </p>
              </Panel>
            </div>

            {/* Provenance */}
            <footer className="mt-4 px-1 font-mono text-[11px] leading-relaxed text-[var(--dim)]">
              Source: interpreter on this host (:8787, /feed/all +
              /feed/signals), polling
              every ~30s from gex.stepdad.finance RTD (
              {display.rtdStrikes ?? "—"} strikes realtime) + Nasdaq public
              chain ({display.nasdaqStrikes ?? "—"} strikes, ~15min delayed
              {display.nasdaqStale ? ", STALE cache" : ""}, as of{" "}
              {fmtTime(display.nasdaqAsOf)} PT). This page polls every 15s
              while open and stores one snapshot per minute for the trail;
              the 5-minute tape.db logger runs separately. GEX convention:
              dealers long calls / short puts; pinning/regime reads only — no
              directional signal is computed.
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
