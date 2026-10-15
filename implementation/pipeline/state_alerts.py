#!/usr/bin/env python3
"""Loaded-gun state alert + charm-velocity trigger (built 2026-10-14).

From the derivative probe (derivatives_probe.py): GEX velocity/acceleration
carry no lead information, but STATE does. The loaded-gun state =
  expected-move budget_left > 0.50  (most of the day's move unspent)
  AND pin_score < 40                (no pin protection)
  AND net_gex_m < 0                 (negative gamma)
  AND spot < gamma_flip             (amplification side)
Backtest on 8 clean sessions (Oct 2 excluded, pre-fix units): 11 entries,
8/11 followed by a >= $1.39 excursion within 60 min (base rate 25%), and
all 11 saw >= $1.23. State occurs only on negative-gamma days.

Charm velocity (charm_k change over ~30m) is the one derivative with a
pulse (rho -0.19). Threshold -10,000 = bottom-tercile boundary of its
distribution across clean sessions. A charm drop through the threshold
inside the loaded state is a TRIGGER; outside the state it logs silently.

Reads tape.db snapshots only (same grid the probe used). Writes tape.db
table state_events with forward excursions back-scored as rows accrue.
Modes: --live (cron), --backfill YYYY-MM-DD, --report.
"""
import argparse, json, sqlite3, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DB_PATH = "/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db"

BUDGET_MIN = 0.50
PIN_MAX = 40
CHARM_TRIGGER = -10000     # charm_k units per ~30m
CHARM_REARM = -5000
EXIT_ROWS = 2              # consecutive non-loaded rows to exit the state

def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS state_events (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL, ts_utc TEXT NOT NULL, ts_et TEXT NOT NULL,
        type TEXT NOT NULL, spot REAL, budget_left REAL, pin REAL,
        net_gex_m REAL, flip_dist REAL, charm_vel30 REAL, detail TEXT,
        exc30 REAL, exc60 REAL, scored INTEGER DEFAULT 0,
        UNIQUE (ts_utc, type))""")
    return con

def day_rows(con, day):
    rows = con.execute("""SELECT ts, spot, max_pain, gamma_flip, net_gex_m,
        charm_k, pin_score, exp_move_dollars, exp_move_rem_dollars
        FROM snapshots WHERE market_open=1 ORDER BY ts""").fetchall()
    out = []
    for r in rows:
        d = datetime.fromisoformat(r[0]).astimezone(ET).date().isoformat()
        if d == day:
            out.append(r)
    return out

def excursions(rows, i):
    """One-sided forward excursion from rows[i] spot (probe definition)."""
    s = rows[i][1]
    res = {}
    for steps, key in ((6, "exc30"), (12, "exc60")):
        fut = [rows[j][1] for j in range(i + 1, min(len(rows), i + 1 + steps))]
        if len(fut) >= max(2, steps - 2):
            res[key] = round(max(abs(max(fut) - s), abs(min(fut) - s)), 2)
    return res

def detect(rows):
    """Run the state machine over one day's rows; return event dicts."""
    events = []
    full_em = next((r[7] for r in rows if r[7]), None)
    if not full_em:
        return events
    state_on = False; off_streak = 0
    charm_armed = True
    for i, r in enumerate(rows):
        ts, spot, flip, gex, charm, pin, rem = r[0], r[1], r[3], r[4], r[5], r[6], r[8]
        if rem is None or pin is None or not flip:
            continue
        bl = rem / full_em
        flip_dist = spot - flip
        loaded = bl > BUDGET_MIN and pin < PIN_MAX and (gex or 0) < 0 and spot < flip
        cv = None
        if i >= 6 and charm is not None and rows[i - 6][5] is not None:
            cv = charm - rows[i - 6][5]
        base = dict(ts=ts, spot=spot, budget_left=round(bl, 2), pin=pin,
                    net_gex_m=gex, flip_dist=round(flip_dist, 2), charm_vel30=cv)
        if loaded:
            off_streak = 0
            if not state_on:
                state_on = True
                events.append(dict(base, type="loaded_gun_on",
                                   detail={"budget_left": round(bl, 2), "pin": pin,
                                           "net_gex_m": gex, "flip_dist": round(flip_dist, 2)}))
        elif state_on:
            off_streak += 1
            if off_streak >= EXIT_ROWS:
                state_on = False; off_streak = 0
                events.append(dict(base, type="loaded_gun_off", detail={}))
        if cv is not None:
            if cv > CHARM_REARM:
                charm_armed = True
            if charm_armed and cv <= CHARM_TRIGGER:
                charm_armed = False
                events.append(dict(base, type="charm_trigger" if state_on else "charm_vel",
                                   detail={"charm_vel30": round(cv), "state": "loaded" if state_on else "off"}))
    # attach row index for scoring
    idx = {r[0]: i for i, r in enumerate(rows)}
    for e in events:
        e["row_idx"] = idx[e["ts"]]
    return events

def store(con, day, rows, events):
    new = []
    for e in events:
        exc = excursions(rows, e["row_idx"])
        try:
            con.execute("""INSERT INTO state_events
                (day, ts_utc, ts_et, type, spot, budget_left, pin, net_gex_m,
                 flip_dist, charm_vel30, detail, exc30, exc60, scored)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (day, e["ts"], datetime.fromisoformat(e["ts"]).astimezone(ET).strftime("%Y-%m-%d %H:%M"),
                 e["type"], round(e["spot"], 2), e["budget_left"], e["pin"], e["net_gex_m"],
                 e["flip_dist"], e["charm_vel30"], json.dumps(e["detail"]),
                 exc.get("exc30"), exc.get("exc60"), 1 if "exc60" in exc else 0))
            new.append(e)
        except sqlite3.IntegrityError:
            pass
    con.commit()
    return new

def backscore(con):
    """Fill excursions for stored events whose future rows now exist."""
    todo = con.execute("SELECT id, day, ts_utc FROM state_events WHERE scored=0").fetchall()
    by_day = {}
    for eid, day, ts in todo:
        by_day.setdefault(day, []).append((eid, ts))
    for day, items in by_day.items():
        rows = day_rows(con, day)
        idx = {r[0]: i for i, r in enumerate(rows)}
        for eid, ts in items:
            if ts not in idx:
                continue
            exc = excursions(rows, idx[ts])
            if "exc60" in exc:
                con.execute("UPDATE state_events SET exc30=?, exc60=?, scored=1 WHERE id=?",
                            (exc.get("exc30"), exc["exc60"], eid))
    con.commit()

def fmt(e):
    et = datetime.fromisoformat(e["ts"]).astimezone(ET).strftime("%H:%M")
    return (f"{e['type']} | {et} ET | spot {e['spot']:.2f} | budget_left {e['budget_left']} | "
            f"pin {e['pin']} | net_gex {e['net_gex_m']} | flip_dist {e['flip_dist']} | "
            f"charm_vel30 {e['charm_vel30']}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--backfill", metavar="YYYY-MM-DD")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    con = db_connect()

    if args.report:
        for t in ("loaded_gun_on", "charm_trigger", "charm_vel"):
            n, sc, hits, avg = con.execute("""SELECT COUNT(*), SUM(scored),
                SUM(CASE WHEN exc60>=1.39 THEN 1 ELSE 0 END), ROUND(AVG(exc60),2)
                FROM state_events WHERE type=?""", (t,)).fetchone()
            print(f"{t:16} n={n:3} scored={sc or 0:3} exc60>=1.39: {hits or 0}  avg_exc60={avg}")
        return

    if args.backfill:
        if args.backfill == "2026-10-02":
            print("SKIP: 2026-10-02 is on pre-fix GEX/charm scales")
            return
        rows = day_rows(con, args.backfill)
        ev = detect(rows)
        new = store(con, args.backfill, rows, ev)
        backscore(con)
        print(f"backfill {args.backfill}: {len(ev)} events ({len(new)} new)")
        for e in ev:
            print(" ", fmt(e))
        return

    day = datetime.now(ET).date().isoformat()
    rows = day_rows(con, day)
    if not rows:
        print("NO_ROWS")
        return
    ev = detect(rows)
    new = store(con, day, rows, ev)
    backscore(con)
    now = datetime.now(timezone.utc)
    printed = False
    for e in new:
        age_min = (now - datetime.fromisoformat(e["ts"])).total_seconds() / 60
        if e["type"] == "loaded_gun_on" and age_min <= 240:
            print("STATE " + fmt(e)); printed = True
        elif e["type"] == "charm_trigger" and age_min <= 20:
            print("STATE " + fmt(e)); printed = True
        elif e["type"] == "charm_vel" and age_min <= 20:
            print("EVENT " + fmt(e)); printed = True
    if not printed:
        print("QUIET")

if __name__ == "__main__":
    main()
