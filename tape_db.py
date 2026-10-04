"""SQLite store for the 0DTE tape: queryable history of every 5-min snapshot.

DB lives at ~/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db
(survives VM restarts; home dir persists).

Tables:
  snapshots   one row per maxpain_log.py record (spot, max pain, walls, flip,
              regime, pin score, expected move, hedge buckets, reversal read,
              charm/vanna, volume/OI, IV surface, events)
  gex_strikes per-strike net GEX snapshots for the strike x time heatmap
  alerts      alert firings from watcher.py (wired when Anik wants it)

Usage:
  python3 tape_db.py init                       # create tables
  python3 tape_db.py backfill                    # load all JSONL history
  python3 tape_db.py "SELECT ..."                # run a read query
"""
import json
import os
import sqlite3
import sys

HIDDEN = os.path.expanduser("~/workspace/goals/0dte-tape-alert-watch/hidden_files")
DB_PATH = os.path.join(HIDDEN, "tape.db")
LOG_PATH = os.path.join(HIDDEN, "maxpain_history.jsonl")
GEX_PATH = os.path.join(HIDDEN, "gex_history.jsonl")

SNAP_COLS = [
    "ts", "market_open", "expiry", "spot",
    "quote_as_of", "nasdaq_as_of", "src_mix",
    "max_pain", "call_wall", "put_wall", "gamma_flip", "net_gex_m", "gex_formula",
    "gamma_regime",
    "charm_k", "vanna_k",
    "call_volume", "put_volume", "call_oi", "put_oi", "pc_volume", "pc_oi",
    "hottest_strike", "hottest_call_vol", "hottest_put_vol",
    "unusual_count", "unusual_notional_k", "top_unusual",
    "atm_iv", "atm_put_iv", "atm_strike", "rr_25d", "smile_width", "smile_min_strike",
    "top_gamma",
    "exp_move_dollars", "exp_move_pct", "exp_move_rem_dollars", "exp_move_rem_pct",
    "pin_score", "pin_magnet",
    "hedge_25bp_m", "hedge_25bp_dir", "hedge_1pct_m", "hedge_1pct_dir",
    "dealer_gamma_m_per_pt",
    "rev_magnet", "rev_disp_dollars", "rev_stretched", "rev_conditions",
    "events",
]
JSON_COLS = {"top_gamma", "top_unusual", "rev_conditions", "events"}


def connect():
    os.makedirs(HIDDEN, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db(con=None):
    con = con or connect()
    con.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            market_open INTEGER,
            expiry TEXT NOT NULL,
            spot REAL,
            quote_as_of TEXT, nasdaq_as_of TEXT, src_mix TEXT,
            max_pain REAL, call_wall REAL, put_wall REAL, gamma_flip REAL,
            net_gex_m REAL, gamma_regime TEXT,
            gex_formula TEXT,
            charm_k REAL, vanna_k REAL,
            call_volume INTEGER, put_volume INTEGER, call_oi INTEGER, put_oi INTEGER,
            pc_volume REAL, pc_oi REAL,
            hottest_strike REAL, hottest_call_vol INTEGER, hottest_put_vol INTEGER,
            unusual_count INTEGER, unusual_notional_k REAL, top_unusual TEXT,
            atm_iv REAL, atm_put_iv REAL, atm_strike REAL,
            rr_25d REAL, smile_width REAL, smile_min_strike REAL,
            top_gamma TEXT,
            exp_move_dollars REAL, exp_move_pct REAL,
            exp_move_rem_dollars REAL, exp_move_rem_pct REAL,
            pin_score REAL, pin_magnet REAL,
            hedge_25bp_m REAL, hedge_25bp_dir TEXT,
            hedge_1pct_m REAL, hedge_1pct_dir TEXT,
            dealer_gamma_m_per_pt REAL,
            rev_magnet REAL, rev_disp_dollars REAL, rev_stretched INTEGER,
            rev_conditions TEXT,
            events TEXT,
            UNIQUE (ts, expiry)
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS gex_strikes (
            ts TEXT NOT NULL,
            expiry TEXT NOT NULL,
            strike REAL NOT NULL,
            net_gex_m REAL,
            PRIMARY KEY (ts, expiry, strike)
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            detail TEXT
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_snap_expiry ON snapshots(expiry)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(ts)")
    # dedup guard for DBs created before the UNIQUE constraint (F10)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_snap_ts_expiry "
                "ON snapshots(ts, expiry)")
    # migrations for pre-existing DBs (F04/F03): add columns if absent
    for coldef in ("gex_formula TEXT", "quote_as_of TEXT",
                   "nasdaq_as_of TEXT", "src_mix TEXT"):
        try:
            con.execute(f"ALTER TABLE snapshots ADD COLUMN {coldef}")
        except Exception:
            pass  # column already exists
    con.commit()


def _norm(rec):
    vals = []
    for c in SNAP_COLS:
        v = rec.get(c)
        if c in JSON_COLS and v is not None:
            v = json.dumps(v)
        if c == "rev_stretched" and v is not None:
            v = 1 if v else 0
        if c == "market_open" and v is not None:
            v = 1 if v else 0
        vals.append(v)
    return vals


def insert_snapshot(rec, con=None):
    con = con or connect()
    cols = ", ".join(SNAP_COLS)
    qs = ", ".join("?" * len(SNAP_COLS))
    con.execute(f"INSERT OR IGNORE INTO snapshots ({cols}) VALUES ({qs})", _norm(rec))
    con.commit()


def insert_gex_snapshot(ts, expiry, gex_m, con=None):
    """gex_m: {strike_str: net_gex_m}"""
    con = con or connect()
    rows = [(ts, expiry, float(k), v) for k, v in gex_m.items()]
    con.executemany(
        "INSERT OR IGNORE INTO gex_strikes (ts, expiry, strike, net_gex_m) VALUES (?,?,?,?)",
        rows)
    con.commit()


def has_snapshot(con, ts, expiry):
    return con.execute(
        "SELECT 1 FROM snapshots WHERE ts = ? AND expiry = ?",
        (ts, expiry)).fetchone() is not None


def mirror_record(rec, gex_m, con=None):
    """Insert a logger record + its gex rows in ONE transaction (F10).
    INSERT OR IGNORE on (ts, expiry): re-running the same invocation is a
    no-op, never a duplicate."""
    con = con or connect()
    cols = ", ".join(SNAP_COLS)
    qs = ", ".join("?" * len(SNAP_COLS))
    with con:  # single transaction; auto-rollback on error (F10)
        con.execute(f"INSERT OR IGNORE INTO snapshots ({cols}) VALUES ({qs})",
                    _norm(rec))
        if gex_m:
            rows = [(rec["ts"], rec["expiry"], float(k), v)
                    for k, v in gex_m.items()]
            con.executemany(
                "INSERT OR IGNORE INTO gex_strikes (ts, expiry, strike, net_gex_m)"
                " VALUES (?,?,?,?)", rows)


def insert_alert(ts, alert_type, detail="", con=None):
    con = con or connect()
    con.execute("INSERT INTO alerts (ts, alert_type, detail) VALUES (?,?,?)",
                (ts, alert_type, detail))
    con.commit()


def backfill(con=None, dry_run=False):
    """Additive backfill: never deletes rows; INSERT OR IGNORE makes re-runs
    idempotent (F10). Returns dict with accepted/rejected/ignored counts."""
    con = con or connect()
    counts = {"snap_accepted": 0, "snap_ignored": 0, "snap_rejected": 0,
              "gex_accepted": 0, "gex_ignored": 0, "gex_rejected": 0}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ts, expiry = rec.get("ts"), rec.get("expiry")
                    if not ts or not expiry:
                        counts["snap_rejected"] += 1
                        continue
                    if dry_run:
                        counts["snap_ignored" if has_snapshot(con, ts, expiry)
                               else "snap_accepted"] += 1
                        continue
                    before = con.total_changes
                    insert_snapshot(rec, con)
                    if con.total_changes > before:
                        counts["snap_accepted"] += 1
                    else:
                        counts["snap_ignored"] += 1
                except Exception:
                    counts["snap_rejected"] += 1
    if os.path.exists(GEX_PATH):
        with open(GEX_PATH) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    ts, expiry = d.get("ts"), d.get("expiry")
                    gex_m = d.get("gex_m") or {}
                    if not ts or not expiry or not gex_m:
                        counts["gex_rejected"] += 1
                        continue
                    if dry_run:
                        counts["gex_accepted"] += 1
                        continue
                    before = con.total_changes
                    insert_gex_snapshot(ts, expiry, gex_m, con)
                    if con.total_changes > before:
                        counts["gex_accepted"] += 1
                    else:
                        counts["gex_ignored"] += 1
                except Exception:
                    counts["gex_rejected"] += 1
    return counts


def stats(con=None):
    con = con or connect()
    out = {}
    out["snapshots"] = con.execute("SELECT COUNT(*) c FROM snapshots").fetchone()["c"]
    out["gex_rows"] = con.execute("SELECT COUNT(*) c FROM gex_strikes").fetchone()["c"]
    out["alerts"] = con.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]
    out["days"] = [r["expiry"] for r in
                   con.execute("SELECT DISTINCT expiry FROM snapshots ORDER BY expiry")]
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    con = connect()
    init_db(con)
    if cmd == "init":
        print(f"db ready at {DB_PATH}")
    elif cmd == "backfill":
        dry = "--dry-run" in sys.argv
        counts = backfill(con, dry_run=dry)
        print(f"backfill{' DRY RUN' if dry else ''}: {json.dumps(counts)}")
        print(json.dumps(stats(con), indent=1))
    elif cmd == "stats":
        print(json.dumps(stats(con), indent=1))
    else:
        # treat the arg as a SQL query (read-only guard)
        sql = " ".join(sys.argv[1:])
        if not sql.strip().lower().startswith("select"):
            print("only SELECT queries allowed on the command line")
            sys.exit(1)
        rows = con.execute(sql).fetchall()
        print(f"{len(rows)} rows")
        for r in rows[:50]:
            print(dict(r))
