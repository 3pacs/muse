#!/usr/bin/env python3
"""
Catalytic early detection — wall-test grading (built 2026-10-15).

Anik's doctrine: "the wall is dictated by the volume spikes and follow up
moves." A GEX/OI wall is only a claim. Its strength is proven by tape
behavior at the level: big volume printing there and price getting
rejected (strong wall), or price crossing on ordinary volume and holding
beyond it (weak wall / acceptance).

This scorer watches SPY 1-min bars against the prevailing call/put walls
(from tape.db snapshots, 5-min grid) and grades every test episode:

  - break   : a 1-min close through the wall after a test episode.
  - defense : price tested the wall (within $0.35) and retreated >= $1.00
              without a close through it — the wall held.

Each episode records the peak 1-min volume multiple during the test
(vs the trailing-30 median, on the tracker's phantom-sanitized bars):
  quiet < 3x | active 3-6x | spike >= 6x (or MEGA: >= 800k and >= 4x).

Follow-through is scored at +30m (re-checked at +60m): for a break,
'accepted' if spot holds beyond the wall, 'rejected' if it falls back
$0.50+ inside; for a defense the outcome is 'rejected' (wall held) with
the bounce distance as follow-through. Outcomes mature over later runs;
only first stores are printed in --live mode.

Rows land in tape.db `wall_tests`. Modes:
  --live              today's session; print CATALYST lines for new rows
  --backfill DAY      score a past session (Yahoo 1-min reaches ~5 days)
  --report            print stored grades

Usage: python3 wall_tests.py --live
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from statistics import median
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicator_tracker import fetch_bars  # phantom-sanitized 1-min bars

DB_PATH = "/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db"
ET = ZoneInfo("America/New_York")

TEST_BAND = 0.35      # bar extreme within this of the wall = a test
RETREAT = 1.00        # move away from wall that confirms a defense
REARM_DIST = 1.50     # after an episode, price must leave by this to re-test
SPIKE_MULT = 6.0
MEGA_VOL = 800_000
MEGA_MULT = 4.0


def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS wall_tests (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL, ts_utc TEXT NOT NULL, ts_et TEXT NOT NULL,
        side TEXT NOT NULL, wall REAL, kind TEXT NOT NULL,
        vol_mult REAL, vol_class TEXT, peak_vol INTEGER,
        outcome TEXT, ft30 REAL, detail TEXT,
        UNIQUE (day, ts_utc, side, kind))""")
    return con


def day_snapshots(con, day):
    rows = con.execute("""SELECT ts, spot, call_wall, put_wall FROM snapshots
                          WHERE market_open=1 ORDER BY ts""").fetchall()
    out = []
    for ts, spot, cw, pw in rows:
        dt = datetime.fromisoformat(ts)
        if dt.astimezone(ET).date().isoformat() == day:
            out.append([dt, spot, cw, pw])
    # Anti-flicker: a wall level only becomes effective after it appears
    # in 2 consecutive snapshots (~10 min). Single-snapshot excursions
    # (e.g. call wall 772 -> 773 -> 772 on 2026-10-15) are data flicker,
    # not levels, and must not spawn phantom tests or breaks.
    eff_c = eff_p = None
    prev_c = prev_p = None
    for r in out:
        if eff_c is None:
            eff_c, eff_p = r[2], r[3]
        else:
            if r[2] == prev_c:
                eff_c = r[2]
            if r[3] == prev_p:
                eff_p = r[3]
        prev_c, prev_p = r[2], r[3]
        r[2], r[3] = eff_c, eff_p
    return [tuple(r) for r in out]


def vol_class(mult, peak):
    if mult is None:
        return "unknown"
    if mult >= SPIKE_MULT or (peak >= MEGA_VOL and mult >= MEGA_MULT):
        return "spike"
    if mult >= 3.0:
        return "active"
    return "quiet"


def episodes(bars, snaps):
    """Run the test-episode state machine for both walls over 1-min bars.

    bars: (ts_utc, o, h, l, c, v). snaps: (dt_utc, spot, call_wall, put_wall)
    with dt tz-aware. Returns episode dicts (outcome left pending to score).
    """
    if not bars or not snaps:
        return []
    vols = [b[5] for b in bars]
    mults = []
    for i, v in enumerate(vols):
        if i >= 10:
            m = median(vols[max(0, i - 30):i])
            mults.append(v / m if m > 0 else None)
        else:
            mults.append(None)

    def wall_at(ts_utc, idx):
        w = None
        for dt, _s, cw, pw in snaps:
            if dt <= ts_utc:
                w = cw if idx == 2 else pw
            else:
                break
        return w

    found = []
    for side, widx, is_call in (("call", 2, True), ("put", 3, False)):
        ep = None  # active episode dict
        cool_wall = None  # wall of the last resolved episode, while cooling
        for i, b in enumerate(bars):
            ts, o, h, l, c, v = b
            wall = wall_at(ts, widx)
            if wall is None:
                continue
            if cool_wall is not None:
                # hover-chop guard: after an episode resolves at a wall,
                # spot must retreat REARM_DIST back inside (or the wall
                # itself must reprice >= $1) before a new episode counts.
                if abs(wall - cool_wall) >= 1.0:
                    cool_wall = None
                elif is_call and c <= cool_wall - REARM_DIST:
                    cool_wall = None
                elif not is_call and c >= cool_wall + REARM_DIST:
                    cool_wall = None
            if ep is None:
                if cool_wall is not None:
                    continue
                # start a test when the bar's extreme reaches the band
                tests = (h >= wall - TEST_BAND) if is_call else (l <= wall + TEST_BAND)
                if tests:
                    ep = {"side": side, "wall": wall, "start_i": i,
                          "peak_vol": v, "peak_mult": mults[i]}
                continue
            # inside an episode: track peak volume
            if v > ep["peak_vol"]:
                ep["peak_vol"] = v
                ep["peak_mult"] = mults[i]
            broke = (c > wall) if is_call else (c < wall)
            if broke:
                ep.update(kind="break", end_i=i)
                found.append(ep)
                cool_wall = ep["wall"]
                ep = None
                continue
            retreated = (c <= wall - RETREAT) if is_call else (c >= wall + RETREAT)
            if retreated:
                ep.update(kind="defense", end_i=i,
                          ft30=round(abs(c - wall), 2))
                found.append(ep)
                cool_wall = ep["wall"]
                ep = None
                continue
            # wall repriced away mid-episode: abandon quietly
            if abs(wall - ep["wall"]) >= 1.0:
                ep = None
    return found


def score_outcome(bars, ep):
    """Follow-through for a resolved episode, from bars after its end."""
    end_i = ep["end_i"]
    wall = ep["wall"]
    is_call = ep["side"] == "call"
    if ep["kind"] == "defense":
        return "rejected", ep.get("ft30")
    last_is_close = bars[-1][0].astimezone(ET).strftime("%H:%M") >= "15:59"
    for horizon_min in (30, 60):
        j = end_i + horizon_min
        if j >= len(bars):
            if not last_is_close:
                return "pending", None
            j = len(bars) - 1  # session over: the close is the final read
        c = bars[j][4]
        beyond = (c >= wall) if is_call else (c <= wall)
        back = (c < wall - 0.50) if is_call else (c > wall + 0.50)
        if beyond:
            return "accepted", round(abs(c - wall), 2)
        if back:
            return "rejected", round(abs(c - wall), 2)
    return "pending", None


def run_day(con, day, live):
    snaps = day_snapshots(con, day)
    bars = fetch_bars(day, "SPY")
    if not bars:
        print("NO_BARS")
        return
    eps = episodes(bars, snaps)
    new_lines = []
    for ep in eps:
        outcome, ft = score_outcome(bars, ep)
        ts = bars[ep["end_i"]][0]
        vc = vol_class(ep["peak_mult"], ep["peak_vol"])
        detail = {"start_et": bars[ep["start_i"]][0].astimezone(ET).strftime("%H:%M"),
                  "peak_mult": round(ep["peak_mult"], 1) if ep["peak_mult"] else None}
        cur = con.execute("""INSERT OR IGNORE INTO wall_tests
            (day, ts_utc, ts_et, side, wall, kind, vol_mult, vol_class,
             peak_vol, outcome, ft30, detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (day, ts.isoformat(), ts.astimezone(ET).isoformat(), ep["side"],
             ep["wall"], ep["kind"],
             round(ep["peak_mult"], 2) if ep["peak_mult"] else None,
             vc, ep["peak_vol"], outcome, ft, json.dumps(detail)))
        if cur.rowcount:
            # alert on breaks (any volume) and on loud defenses (catalyst:
            # big volume showed up at the wall and got rejected)
            if ep["kind"] == "break" or vc == "spike":
                new_lines.append(
                    f"CATALYST SPY {ep['kind']} {ep['side']}_wall {ep['wall']:.0f} "
                    f"{ts.astimezone(ET).isoformat()} "
                    f"{{\"vol_mult\": {detail['peak_mult']}, \"vol_class\": \"{vc}\", "
                    f"\"peak_vol\": {ep['peak_vol']}, \"outcome\": \"{outcome}\"}}")
        else:
            # mature the outcome on an already-stored row
            con.execute("""UPDATE wall_tests SET outcome=?, ft30=?
                           WHERE day=? AND ts_utc=? AND side=? AND kind=?
                             AND (outcome='pending' OR outcome IS NULL)""",
                        (outcome, ft, day, ts.isoformat(), ep["side"], ep["kind"]))
    con.commit()
    if live:
        print("\n".join(new_lines) if new_lines else "QUIET")
    else:
        print(f"{day}: {len(eps)} episodes scored, {len(new_lines)} alert-grade")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--backfill", metavar="YYYY-MM-DD")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    con = db_connect()
    if a.report:
        rows = con.execute("""SELECT day, ts_et, side, wall, kind, vol_mult,
            vol_class, peak_vol, outcome, ft30 FROM wall_tests
            ORDER BY day DESC, ts_et LIMIT 40""").fetchall()
        for r in rows:
            print(r)
        return
    if a.backfill:
        run_day(con, a.backfill, live=False)
        return
    day = datetime.now(ET).date().isoformat()
    run_day(con, day, live=True)


if __name__ == "__main__":
    main()
