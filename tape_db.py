"""SQLite store for the 0DTE tape: queryable history of every 5-min snapshot.

DB lives at ~/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db
(survives VM restarts; home dir persists).

Tables:
  snapshots   one row per maxpain_log.py record (spot, max pain, walls, flip,
              regime, pin score, expected move, hedge buckets, reversal read,
              charm/vanna, volume/OI, IV surface, events)
  gex_strikes per-strike net GEX snapshots for the strike x time heatmap
  alerts      alert firings from watcher.py (wired when Anik wants it)
  mirror_conflicts  quarantine receipts for changed-payload re-mirrors (R4)

Identity policy (R4):
  (ts, expiry) is the event identity; payload_hash covers the full record +
  strike map. Identical identity+hash -> explicit duplicate (no-op). Same
  identity with a changed payload -> explicit CONFLICT: the first record
  stands, no partial strike merge, and the attempt is receipted in
  mirror_conflicts. A receipt clock alone never creates a new event.

Usage:
  python3 tape_db.py init                       # create tables
  python3 tape_db.py backfill                    # load all JSONL history
  python3 tape_db.py "SELECT ..."                # run a read query
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

HIDDEN = os.path.expanduser("~/workspace/goals/0dte-tape-alert-watch/hidden_files")
DB_PATH = os.path.join(HIDDEN, "tape.db")
LOG_PATH = os.path.join(HIDDEN, "maxpain_history.jsonl")
GEX_PATH = os.path.join(HIDDEN, "gex_history.jsonl")

SNAP_COLS = [
    "ts", "market_open", "expiry", "spot",
    "quote_as_of", "nasdaq_as_of", "src_mix",
    "max_pain", "call_wall", "put_wall", "gamma_flip", "net_gex_m", "gex_formula",
    # J1-C: units lineage is semantic — incompatible units are a conflict.
    "gex_units",
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

# J1: one authoritative accepted event. The semantic payload is the
# canonical core below: every SNAP_COLS field, normalized so the journal
# record, the DB row and a replayed line all canonicalize identically.
# Receipt clocks (logged_at and friends) are never semantic: they are not
# in SNAP_COLS and are excluded from the hash. The strike map is compared
# separately (see canonical_strikes); journal snapshot lines that predate
# the embedded strike map compare on the core only.
RECEIPT_FIELDS = {"logged_at"}


def normalize_ts(ts):
    """Canonical event-time identity: aware timestamps fold to UTC ISO.

    Equivalent instants written with different offsets ('14:00+00:00' vs
    '10:00-04:00') share one identity. Unparseable/naive values keep their
    raw string (never silently rewritten)."""
    if not isinstance(ts, str):
        return ts
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return ts
    if dt.tzinfo is None:
        return ts
    return dt.astimezone(timezone.utc).isoformat()


def _canon_num(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def _canon_val(col, v):
    """Normalize one column value so journal dicts and DB rows agree."""
    if v is None:
        return None
    if col in JSON_COLS:
        try:
            obj = json.loads(v) if isinstance(v, str) else v
        except (ValueError, TypeError):
            return str(v)
        try:
            return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                              default=str)
        except (ValueError, TypeError):
            return str(obj)
    if col in ("rev_stretched", "market_open"):
        return 1 if v else 0
    return _canon_num(v)


def event_core(rec):
    """Canonical semantic payload of an event (no strike map, no receipt
    fields). Two records describing the same accepted event produce equal
    dicts whether they come from the journal, the DB row or a replay."""
    core = {}
    for c in SNAP_COLS:
        v = rec.get(c)
        if c == "ts":
            v = normalize_ts(v)
        core[c] = _canon_val(c, v)
    return core


def core_hash(core):
    return hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"),
                   default=str).encode()).hexdigest()


# J1-B: sentinel for "strike map unavailable" (not provided), distinct from
# an explicitly empty map {}. Missing/unavailable content is never treated
# as a change; explicitly empty content is.
_MAP_UNAVAILABLE = object()


def semantic_hash(core, smap):
    """J1-B: full semantic hash — core plus strike map. Changed strikes (or
    a changed formula, via the core) produce distinct kept/incoming hashes
    on conflict receipts."""
    h = hashlib.sha256()
    h.update(json.dumps(core, sort_keys=True, separators=(",", ":"),
                        default=str).encode())
    h.update(b"\x00")
    h.update(json.dumps(smap if isinstance(smap, dict) else {},
                        sort_keys=True, separators=(",", ":"),
                        default=str).encode())
    return h.hexdigest()


def _strike_key(k):
    try:
        return str(float(k))
    except (ValueError, TypeError):
        return str(k)


def canonical_strikes(gex_m):
    """Normalized strike map: canonical keys, float values, sorted."""
    out = {}
    for k, v in (gex_m or {}).items():
        try:
            out[_strike_key(k)] = float(v)
        except (ValueError, TypeError):
            continue
    return out


def _map_status(gex_m):
    """J1-C: map availability status for persistence.
    'explicit' — non-empty map provided.
    'explicit_empty' — empty map explicitly provided ({}).
    'unavailable' — no map provided (None/missing)."""
    if gex_m is None:
        return "unavailable"
    if isinstance(gex_m, dict) and len(gex_m) == 0:
        return "explicit_empty"
    if isinstance(gex_m, dict):
        return "explicit"
    return "unavailable"


def _resolve_identity(con, ts_norm, expiry):
    """J1-C: additive legacy timestamp alias policy. Returns the actual
    stored ts for an identity, None if absent, or _AMBIGUOUS if multiple
    distinct rows normalize to the same instant (J1-D: ambiguous aliases
    are quarantined, not arbitrarily resolved). J1-E: compares the full
    canonical core plus strike map/status — matching spot/formula alone
    is insufficient. Raw history is never rewritten."""
    # J1-D: always scan for all matching aliases to detect ambiguity.
    try:
        rows = con.execute(
            "SELECT ts FROM snapshots WHERE expiry = ?",
            (expiry,)).fetchall()
    except Exception:
        return None
    matches = []
    for r in rows:
        try:
            if normalize_ts(r["ts"]) == ts_norm:
                matches.append(r["ts"])
        except Exception:
            continue
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # J1-E: multiple aliases — compare full canonical core + map.
    # Fetch each candidate's full content.
    def _content(ts):
        row = con.execute(
            "SELECT * FROM snapshots WHERE ts = ? AND expiry = ?",
            (ts, expiry)).fetchone()
        if row is None:
            return None
        rec = {c: row[c] for c in SNAP_COLS if c in row.keys()}
        core = event_core(rec)
        strikes = canonical_strikes(
            {r["strike"]: r["net_gex_m"]
             for r in con.execute(
                 "SELECT strike, net_gex_m FROM gex_strikes WHERE ts = ? AND expiry = ?",
                 (ts, expiry))})
        try:
            status = row["gex_map_status"]
        except Exception:
            status = "unavailable"
        return (core, strikes, status)
    first = _content(matches[0])
    if first is None:
        return _AMBIGUOUS
    for ts in matches[1:]:
        other = _content(ts)
        if other != first:
            return _AMBIGUOUS
    return matches[0]


# J1-D: sentinel for ambiguous legacy aliases (multiple distinct rows,
# same normalized instant). Callers must quarantine, not pick one.
_AMBIGUOUS = object()


def classify_event(stored_core, incoming_core):
    """The ONE duplicate/conflict decision (J1): logger, mirror and backfill
    all route through here. Returns 'new', 'duplicate' or 'conflict'."""
    if stored_core is None:
        return "new"
    return "duplicate" if stored_core == incoming_core else "conflict"


def fetch_stored(con, ts, expiry):
    """Reconstruct the accepted event from the DB projection: canonical core
    from the snapshot row + strike map from gex_strikes. Returns
    (core, strikes, map_status, digest) or (None, None, None, None) when
    nothing is stored. Uses J1-C legacy alias resolution for
    pre-normalization rows. The map_status is 'explicit' / 'explicit_empty'
    / 'unavailable' (J1-C); rows predating the status column report
    'unavailable'. The digest is the stored payload_hash (full semantic
    hash). Used for validated legacy comparison — never blind hash adoption."""
    ts_norm = normalize_ts(ts)
    stored_ts = _resolve_identity(con, ts_norm, expiry)
    if stored_ts is None:
        return None, None, None, None
    # J1-D: detect ambiguous aliases (multiple rows, different content).
    # _resolve_identity returns _AMBIGUOUS in that case.
    if stored_ts is _AMBIGUOUS:
        return _AMBIGUOUS, None, None, None
    row = con.execute(
        "SELECT * FROM snapshots WHERE ts = ? AND expiry = ?",
        (stored_ts, expiry)).fetchone()
    if row is None:
        return None, None, None, None
    rec = {c: row[c] for c in SNAP_COLS if c in row.keys()}
    strikes = canonical_strikes(
        {r["strike"]: r["net_gex_m"]
         for r in con.execute(
             "SELECT strike, net_gex_m FROM gex_strikes WHERE ts = ? AND expiry = ?",
             (stored_ts, expiry))})
    try:
        status = row["gex_map_status"]
    except Exception:
        status = None
    # J1-C: a stored status is authoritative; without one, infer from
    # surviving rows (non-empty projection implies an explicit map, but an
    # empty projection is unavailable, not empty — see lost_map fixture).
    if status not in ("explicit", "explicit_empty", "unavailable"):
        status = "explicit" if strikes else "unavailable"
    try:
        digest = row["payload_hash"]
    except Exception:
        digest = None
    return event_core(rec), strikes, status, digest


def rec_from_row(con, ts, expiry):
    """Rebuild the accepted journal record from the DB projection (inverse
    of _norm, best-effort). Used to repair a missing journal line after a
    crash when the DB is the only surviving projection. J1-D: uses legacy
    alias resolution so the same identity resolves consistently."""
    ts_norm = normalize_ts(ts)
    stored_ts = _resolve_identity(con, ts_norm, expiry)
    if stored_ts is None or stored_ts is _AMBIGUOUS:
        return None
    row = con.execute(
        "SELECT * FROM snapshots WHERE ts = ? AND expiry = ?",
        (stored_ts, expiry)).fetchone()
    if row is None:
        return None
    rec = {}
    for c in SNAP_COLS:
        if c not in row.keys():
            continue
        v = row[c]
        if c in JSON_COLS and isinstance(v, str):
            try:
                v = json.loads(v)
            except (ValueError, TypeError):
                pass
        if c in ("rev_stretched", "market_open") and v is not None:
            v = bool(v)
        rec[c] = v
    strikes = {r["strike"]: r["net_gex_m"] for r in con.execute(
        "SELECT strike, net_gex_m FROM gex_strikes WHERE ts = ? AND expiry = ?",
        (stored_ts, expiry))}
    if strikes:
        rec["gex_m"] = {_strike_key(k): v for k, v in strikes.items()}
    return rec


def record_conflict(con, ts, expiry, kept_hash, incoming_hash, reason,
                    commit=True):
    """Quarantine receipt for a changed-payload attempt. The accepted event
    stands; the incoming payload never becomes a projection."""
    ts = normalize_ts(ts)
    try:
        con.execute(
            "INSERT INTO mirror_conflicts "
            "(ts, expiry, kept_hash, incoming_hash, received_at, reason) "
            "VALUES (?,?,?,?,?,?)",
            (ts, expiry, kept_hash or "", incoming_hash or "",
             datetime.now(timezone.utc).isoformat(), reason))
    except Exception:
        # pre-migration table without the reason column
        con.execute(
            "INSERT INTO mirror_conflicts "
            "(ts, expiry, kept_hash, incoming_hash, received_at) "
            "VALUES (?,?,?,?,?)",
            (ts, expiry, kept_hash or "", incoming_hash or "",
             datetime.now(timezone.utc).isoformat()))
    if commit:
        con.commit()
    return {"status": "conflict", "reason": reason,
            "kept": kept_hash, "incoming": incoming_hash}


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
            gex_units TEXT,
            gex_map_status TEXT,
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
    # R4: quarantine receipts for changed-payload re-mirrors of the same
    # (ts, expiry) identity. First record stands; conflicts never merge.
    con.execute("""
        CREATE TABLE IF NOT EXISTS mirror_conflicts (
            id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            expiry TEXT NOT NULL,
            kept_hash TEXT NOT NULL,
            incoming_hash TEXT NOT NULL,
            received_at TEXT NOT NULL
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_snap_expiry ON snapshots(expiry)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(ts)")
    # dedup guard for DBs created before the UNIQUE constraint (F10)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_snap_ts_expiry "
                "ON snapshots(ts, expiry)")
    # migrations for pre-existing DBs (F04/F03/R4): add columns if absent
    # J1-C: gex_units (semantic lineage) and gex_map_status (explicit /
    # explicit_empty / unavailable) are compatibility metadata; existing
    # rows without them are treated as unavailable, never rewritten.
    for coldef in ("gex_formula TEXT", "quote_as_of TEXT",
                   "nasdaq_as_of TEXT", "src_mix TEXT",
                   "payload_hash TEXT", "gex_units TEXT",
                   "gex_map_status TEXT"):
        try:
            con.execute(f"ALTER TABLE snapshots ADD COLUMN {coldef}")
        except Exception:
            pass  # column already exists
    # J1: conflict receipts carry the reason the payload was rejected.
    try:
        con.execute("ALTER TABLE mirror_conflicts ADD COLUMN reason TEXT")
    except Exception:
        pass  # column already exists
    # R6: formula tag travels with strike rows (joinable to the snapshot row)
    try:
        con.execute("ALTER TABLE gex_strikes ADD COLUMN gex_formula TEXT")
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


def _payload_hash(rec, gex_m=None):
    """J1-B: canonical semantic hash — core plus strike map. The map comes
    from the explicit gex_m argument, else the record's embedded gex_m,
    else unavailable (hashes as empty). Receipt clocks stay excluded and
    ts stays normalized, as in J1."""
    if gex_m is None:
        gm = rec.get("gex_m")
        gex_m = gm if isinstance(gm, dict) else {}
    return semantic_hash(event_core(rec), canonical_strikes(gex_m))


def insert_snapshot(rec, con=None):
    # J1-B: every writer persists the canonical UTC identity. The raw
    # original timestamp stays preserved in the journal; the DB is keyed
    # by the normalized instant so equivalent-offset writes converge.
    # J1-C: persist the embedded map's availability status.
    con = con or connect()
    rec_n = dict(rec)
    rec_n["ts"] = normalize_ts(rec_n.get("ts"))
    cols = ", ".join(SNAP_COLS + ["payload_hash", "gex_map_status"])
    qs = ", ".join("?" * (len(SNAP_COLS) + 2))
    gm = rec_n.get("gex_m")
    status = _map_status(gm if isinstance(gm, dict) else None)
    con.execute(f"INSERT OR IGNORE INTO snapshots ({cols}) VALUES ({qs})",
                _norm(rec_n) + [_payload_hash(rec_n), status])
    con.commit()


def insert_gex_snapshot(ts, expiry, gex_m, con=None, formula=None):
    """gex_m: {strike_str: net_gex_m}; formula: 'v1'/'v2'/None (R6)."""
    con = con or connect()
    ts = normalize_ts(ts)
    rows = [(ts, expiry, float(k), v, formula) for k, v in gex_m.items()]
    con.executemany(
        "INSERT OR IGNORE INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula)"
        " VALUES (?,?,?,?,?)",
        rows)
    con.commit()


def has_snapshot(con, ts, expiry):
    # J1-C: use legacy alias resolution for pre-normalization rows.
    return _resolve_identity(con, normalize_ts(ts), expiry) is not None


def mirror_record(rec, gex_m, con=None):
    """J1: the single duplicate/conflict decision, shared by logger, direct
    mirror and backfill.

      * no stored event                      -> "inserted"
      * same identity + equal canonical core -> "duplicate" (no-op; a
        validated legacy NULL hash is filled in, never blind-adopted)
      * same identity + changed core         -> "conflict": the accepted
        event stands, NO strike merge, attempt receipted in mirror_conflicts
        with a reason. A rejected payload cannot add a strike.

    Strike maps are compared alongside the core: same core but changed
    strikes is also a conflict. Returns {"status": ...}."""
    con = con or connect()
    ts, expiry = normalize_ts(rec["ts"]), rec["expiry"]
    incoming_core = event_core(rec)
    incoming_strikes = canonical_strikes(gex_m)
    # J1-B: full semantic hash (core + strike map) for storage and receipts.
    incoming_full = semantic_hash(incoming_core, incoming_strikes)
    formula = rec.get("gex_formula")
    with con:  # single transaction; auto-rollback on error (F10)
        stored_core, stored_strikes, stored_status, stored_digest = fetch_stored(con, ts, expiry)
        # J1-D: ambiguous legacy aliases are quarantined.
        if stored_core is _AMBIGUOUS:
            return record_conflict(
                con, ts, expiry, None, None,
                "ambiguous legacy timestamp aliases with conflicting "
                "payloads; quarantined, not resolved", commit=False)
        if stored_core is not None:
            # J1-B: full semantic hashes on receipts so a strike-only change
            # yields distinct kept/incoming hashes.
            kept_full = semantic_hash(stored_core, stored_strikes)
            # J1-E: a present stored digest must match the incoming. A
            # mismatch is proof of tampering, not a duplicate — even if
            # core and strikes happen to match.
            if stored_digest is not None and stored_digest != incoming_full:
                return record_conflict(
                    con, ts, expiry, stored_digest, incoming_full,
                    "stored digest mismatch: retained accepted digest does "
                    "not match incoming; quarantined, not adopted",
                    commit=False)
            # J1: legacy NULL hashes are VALIDATED by reconstructing the
            # stored accepted content, never by adopting the incoming hash.
            if stored_digest is None:
                if stored_core == incoming_core and stored_strikes == incoming_strikes:
                    # Use resolved ts for the UPDATE.
                    stored_ts = _resolve_identity(con, ts, expiry)
                    if stored_ts is not None and stored_ts is not _AMBIGUOUS:
                        con.execute("UPDATE snapshots SET payload_hash = ? "
                                    "WHERE ts = ? AND expiry = ?",
                                    (incoming_full, stored_ts, expiry))
                    return {"status": "duplicate", "legacy_validated": True}
                return record_conflict(
                    con, ts, expiry, kept_full, incoming_full,
                    "legacy NULL hash: stored content differs from incoming; "
                    "quarantined, not adopted", commit=False)
            decision = classify_event(stored_core, incoming_core)
            strikes_ok = (stored_strikes == incoming_strikes)
            # J1-C: integrity — if the stored map was explicit (nonempty)
            # but the projection rows are lost, we cannot verify a duplicate.
            # An explicitly empty incoming map against a lost nonempty
            # projection is an integrity mismatch, not a duplicate.
            if (decision == "duplicate" and strikes_ok
                    and stored_status == "explicit" and not stored_strikes
                    and _map_status(gex_m) == "explicit_empty"):
                return record_conflict(
                    con, ts, expiry, kept_full, incoming_full,
                    "integrity: stored strike projection lost for explicitly "
                    "nonempty accepted map; cannot verify duplicate",
                    commit=False)
            if decision == "duplicate" and strikes_ok:
                return {"status": "duplicate"}
            reason = ("core payload changed" if decision == "conflict"
                      else "strike map changed for identical core")
            return record_conflict(con, ts, expiry, kept_full, incoming_full,
                                   reason, commit=False)
        cols = ", ".join(SNAP_COLS + ["payload_hash", "gex_map_status"])
        qs = ", ".join("?" * (len(SNAP_COLS) + 2))
        rec_n = dict(rec, ts=ts)
        # J1-C: persist the map availability status with the accepted event.
        con.execute(f"INSERT INTO snapshots ({cols}) VALUES ({qs})",
                    _norm(rec_n) + [incoming_full, _map_status(gex_m)])
        if incoming_strikes:
            rows = [(ts, expiry, float(k), v, formula)
                    for k, v in incoming_strikes.items()]
            con.executemany(
                "INSERT OR IGNORE INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula)"
                " VALUES (?,?,?,?,?)", rows)
    return {"status": "inserted"}


def insert_alert(ts, alert_type, detail="", con=None):
    con = con or connect()
    con.execute("INSERT INTO alerts (ts, alert_type, detail) VALUES (?,?,?)",
                (ts, alert_type, detail))
    con.commit()


class ReplayState:
    """J1: evolving validation state shared by dry-run and real replay.

    Wraps the DB connection with an overlay of events accepted earlier in
    THIS run, so a dry-run simulates exactly what the real run will do
    (intra-file A,A duplicates, A,C,B,A sequences) without writing.
    The single duplicate/conflict decision (classify_event) is used for
    snapshot lines, gex lines and direct mirrors alike."""

    def __init__(self, con):
        self.con = con
        self.events = {}   # (ts, expiry) -> canonical core accepted this run
        self.strikes = {}  # (ts, expiry) -> {skey: value} accepted this run
        # J1-B: idents whose strike map is explicitly defined (embedded
        # journal map, DB projection, or an accepted gex line). An undefined
        # map is unavailable, not empty.
        self.map_defined = set()
        # J1-D: full accepted payload digest per ident, for proof of
        # original content before repair.
        self.digests = {}

    @staticmethod
    def ident(ts, expiry):
        return (normalize_ts(ts), expiry)

    def stored(self, ts, expiry):
        """Returns (core, strikes, map_defined, digest). core is None when
        no event is stored; core is _AMBIGUOUS when legacy aliases conflict
        (J1-D)."""
        ident = self.ident(ts, expiry)
        if ident in self.events:
            return (self.events[ident], self.strikes.get(ident, {}),
                    ident in self.map_defined, self.digests.get(ident))
        core, smap, status, digest = fetch_stored(self.con, ts, expiry)
        if core is None:
            return None, {}, False, None
        if core is _AMBIGUOUS:
            return _AMBIGUOUS, {}, False, None
        # J1-C: the persisted map status is authoritative. 'explicit' and
        # 'explicit_empty' both define the map; 'unavailable' does not.
        return core, smap, status in ("explicit", "explicit_empty"), digest

    def accept_event(self, ts, expiry, core, smap=_MAP_UNAVAILABLE, digest=None):
        ident = self.ident(ts, expiry)
        self.events[ident] = core
        if smap is not _MAP_UNAVAILABLE:
            self.strikes[ident] = dict(smap)
            self.map_defined.add(ident)
        if digest is not None:
            self.digests[ident] = digest

    def accept_strikes(self, ts, expiry, smap):
        ident = self.ident(ts, expiry)
        cur = dict(self.strikes.get(ident, {}))
        cur.update(smap)
        self.strikes[ident] = cur
        self.map_defined.add(ident)


def _classify_snapshot_line(state, rec):
    """Verdicts 'accepted' | 'duplicate' | 'conflict' | 'rejected'.
    Non-dict lines are rejected, never fatal.
    J1-D: replaces the superset heuristic with proof of original accepted
    content. A duplicate core with an embedded map must prove it is the
    original accepted payload via the full semantic digest; a different
    payload (including a later superset or growth from empty) conflicts.
    Genuine projection loss (same digest, missing rows) repairs."""
    if not isinstance(rec, dict):
        return "rejected"
    ts, expiry = rec.get("ts"), rec.get("expiry")
    if not ts or not expiry:
        return "rejected"
    stored_core, stored_strikes, map_defined, stored_digest = state.stored(ts, expiry)
    # J1-D: ambiguous legacy aliases are quarantined, not resolved.
    if stored_core is _AMBIGUOUS:
        return "conflict"
    decision = classify_event(stored_core, event_core(rec))
    if decision == "new":
        return "accepted"
    if decision == "conflict":
        return "conflict"
    # Duplicate core: verify the embedded map against the accepted digest.
    embedded = _embedded_map(rec)
    # J1-E: an unavailable stored map cannot silently adopt a new map.
    # Without proof of original content, this is a conflict.
    if embedded is not _MAP_UNAVAILABLE and not map_defined:
        return "conflict"
    if embedded is _MAP_UNAVAILABLE or not map_defined:
        return "duplicate"
    # J1-D: compute the incoming full digest and compare with the stored
    # accepted digest. Match = original payload (repair allowed); differ =
    # changed payload (conflict).
    incoming_digest = semantic_hash(event_core(rec), embedded)
    if stored_digest is not None:
        # J1-E: a present digest must match. A mismatch is proof of
        # tampering/divergence, not a legacy case. Do NOT fall through
        # to map comparison.
        return "duplicate" if incoming_digest == stored_digest else "conflict"
    # No stored digest (legacy): fall back to map comparison. An explicitly
    # empty stored map can never grow; otherwise require exact match.
    if embedded == stored_strikes:
        return "duplicate"
    return "conflict"


def _embedded_map(rec):
    """The journal line's embedded strike map, or _MAP_UNAVAILABLE."""
    gm = rec.get("gex_m")
    if not isinstance(gm, dict):
        return _MAP_UNAVAILABLE
    return canonical_strikes(gm)


def _classify_gex_line(state, d):
    """J1-B: secondary strike records validate against the accepted parent.

    Verdicts: 'accepted' | 'duplicate' | 'conflict' | 'orphan' | 'rejected'.
    - No accepted parent event -> 'orphan': quarantined, never accepted.
    - Accepted map undefined -> this line defines it.
    - Accepted map defined -> the line must match it exactly; any value
      change, disjoint addition, or formula change is a conflict. A rejected
      payload never supplements the accepted map."""
    if not isinstance(d, dict):
        return "rejected", {}
    ts, expiry = d.get("ts"), d.get("expiry")
    raw_map = d.get("gex_m")
    if not ts or not expiry or not isinstance(raw_map, dict):
        return "rejected", {}
    smap = canonical_strikes(raw_map)
    if not smap:
        return "rejected", {}
    stored_core, stored_strikes, map_defined, _ = state.stored(ts, expiry)
    if stored_core is None:
        return "orphan", smap
    if stored_core is _AMBIGUOUS:
        return "conflict", smap
    # J1-B: formula/units lineage is semantic — same value with a changed
    # formula is a conflict, not a duplicate.
    stored_formula = stored_core.get("gex_formula")
    incoming_formula = d.get("gex_formula")
    if (stored_formula and incoming_formula
            and stored_formula != incoming_formula):
        return "conflict", smap
    if not map_defined:
        return "accepted", smap
    if stored_strikes == smap:
        return "duplicate", smap
    return "conflict", smap


def backfill(con=None, dry_run=False):
    """Additive backfill: never deletes rows (F10). J1/J1-B: dry-run and real
    replay run the SAME evolving validation/duplicate/conflict state, so
    predicted counts match actual ones. A dry-run never writes. Verdicts:
    accepted / duplicate / conflict (receipted, not inserted) / orphan
    (secondary line without an accepted parent; quarantined) / rejected
    (malformed or non-object)."""
    con = con or connect()
    counts = {"snap_accepted": 0, "snap_duplicate": 0, "snap_conflict": 0,
              "snap_rejected": 0,
              "gex_accepted": 0, "gex_duplicate": 0, "gex_conflict": 0,
              "gex_orphan": 0, "gex_rejected": 0}
    state = ReplayState(con)

    def _lines(path):
        if not os.path.exists(path):
            return
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except Exception:
                    yield None
                    continue
                # J1-B: valid JSON that is not an object is rejected, never
                # fatal; the replay continues with subsequent lines.
                yield parsed if isinstance(parsed, dict) else None

    for rec in _lines(LOG_PATH):
        if rec is None:
            counts["snap_rejected"] += 1
            continue
        verdict = _classify_snapshot_line(state, rec)
        counts["snap_" + verdict] += 1
        ts, expiry = normalize_ts(rec.get("ts")), rec.get("expiry")
        if verdict == "accepted":
            # J1-B: the journal's embedded accepted map rebuilds the
            # secondary strike projection; no separate strike file needed.
            # J1-D: store the full accepted digest for proof before repair.
            embedded = _embedded_map(rec)
            digest = semantic_hash(
                event_core(rec),
                embedded if embedded is not _MAP_UNAVAILABLE else {})
            state.accept_event(ts, expiry, event_core(rec),
                               embedded if embedded is not _MAP_UNAVAILABLE
                               else _MAP_UNAVAILABLE,
                               digest=digest)
            if not dry_run:
                insert_snapshot(rec, con)
                if embedded is not _MAP_UNAVAILABLE and embedded:
                    # The embedded accepted map is part of the snapshot
                    # acceptance (counted under snap_accepted).
                    insert_gex_snapshot(ts, expiry, embedded, con,
                                        formula=rec.get("gex_formula"))
        elif verdict == "conflict" and not dry_run:
            stored_core, _, _, _ = state.stored(ts, expiry)
            record_conflict(
                con, ts, expiry,
                core_hash(stored_core) if stored_core and stored_core is not _AMBIGUOUS else None,
                core_hash(event_core(rec)),
                "backfill: journal line conflicts with accepted event; "
                "not inserted")
        elif verdict == "duplicate":
            # J1-C: reconcile a duplicate accepted journal event — verify
            # the DB strike projection against the embedded accepted map
            # and repair absent rows from accepted content only.
            # J1-E: also repair divergent values, not just missing keys.
            embedded = _embedded_map(rec)
            if embedded is not _MAP_UNAVAILABLE and embedded:
                _, db_strikes, _, _ = state.stored(ts, expiry)
                missing = {k: v for k, v in embedded.items()
                           if k not in db_strikes}
                divergent = {k: v for k, v in embedded.items()
                             if k in db_strikes and db_strikes[k] != v}
                if missing:
                    # Update the overlay so subsequent lines classify
                    # against the repaired projection.
                    state.accept_strikes(ts, expiry, missing)
                    if not dry_run:
                        insert_gex_snapshot(ts, expiry, missing, con,
                                            formula=rec.get("gex_formula"))
                if divergent and not dry_run:
                    # J1-E: repair divergent values via UPDATE on the
                    # resolved actual ts.
                    stored_ts = _resolve_identity(con, ts, expiry)
                    if stored_ts is not None and stored_ts is not _AMBIGUOUS:
                        for k, v in divergent.items():
                            con.execute(
                                "UPDATE gex_strikes SET net_gex_m = ? "
                                "WHERE ts = ? AND expiry = ? AND strike = ?",
                                (v, stored_ts, expiry, float(k)))
                        # Update overlay.
                        state.accept_strikes(ts, expiry, divergent)
    for d in _lines(GEX_PATH):
        if d is None:
            counts["gex_rejected"] += 1
            continue
        verdict, smap = _classify_gex_line(state, d)
        counts["gex_" + verdict] += 1
        ts, expiry = normalize_ts(d.get("ts")), d.get("expiry")
        if verdict == "accepted":
            state.accept_strikes(ts, expiry, smap)
            if not dry_run:
                insert_gex_snapshot(ts, expiry, smap, con,
                                    formula=d.get("gex_formula"))
        elif verdict in ("conflict", "orphan") and not dry_run:
            record_conflict(
                con, ts, expiry, None, None,
                "backfill: " + ("orphan strike line without accepted parent; "
                                "quarantined, not accepted"
                                if verdict == "orphan"
                                else "strike line changes accepted strike map; "
                                "no strike added"))
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
