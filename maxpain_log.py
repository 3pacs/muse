#!/usr/bin/env python3
"""
Max-pain history logger.

Polls the interpreter's /feed/all and appends one record per run to an
append-only JSONL log. Never prunes. Used to study how max pain moves
through the day/week and to hunt for leading indicators.

Log: ~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_history.jsonl
"""

import fcntl
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

LOCK_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_log.lock")

FEED_URL = "http://localhost:8787/feed/all"
LOG_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_history.jsonl")
GEX_SNAP_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/gex_history.jsonl")
EVENTS_PATH = os.path.expanduser("~/workspace/stepdad-0dte/market_events.json")


def fetch():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "stepdad-maxpain-log/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def load_events():
    try:
        with open(EVENTS_PATH) as fh:
            d = json.load(fh)
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    try:
        d = fetch()
    except Exception as e:
        print(f"FEED_DOWN | {e}")
        return
    if d.get("status") != "ok":
        print(f"FEED_ERROR | {d.get('error', 'unknown')}")
        return

    g = d.get("gamma") or {}
    f = d.get("flow") or {}
    iv = d.get("iv") or {}
    vc = d.get("vanna_charm") or {}
    p = d.get("positioning") or {}
    em = p.get("expected_move") or {}
    rw = p.get("reversal_watch") or {}
    buckets = {b.get("shock_bp"): b for b in (p.get("hedge_buckets") or [])}

    top_gamma = g.get("top_strikes") or []
    top_vol = f.get("top_volume_activity") or []
    unusual = f.get("elevated_volume_activity") or []
    top_un = unusual[0] if unusual else None
    smile = iv.get("smile_2pct") or {}

    rec = {
        # J1: one authoritative accepted event. Identity is the feed's own
        # timestamp normalized to UTC (equivalent offsets share one
        # identity); the raw feed string is preserved as ts_original.
        # Replaying the same feed converges; the receipt clock is metadata.
        "ts": None,  # set below after normalization
        "ts_original": (d.get("updated_at") or d.get("quote_as_of")),
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "market_open": d.get("market_open"),
        "expiry": d.get("expiry"),
        "spot": d.get("spot"),
        # provenance (F03): source times + mix survive into history
        "quote_as_of": d.get("quote_as_of"),
        "nasdaq_as_of": ((d.get("sources") or {}).get("nasdaq") or {}).get("as_of"),
        "src_mix": (f"{d.get('n_strikes_rtd_live')} rtd + "
                    f"{d.get('n_strikes_nasdaq_delayed')} nasdaq_delayed"),
        # max pain + gamma structure
        "max_pain": g.get("max_pain"),
        "call_wall": g.get("call_wall"),
        "put_wall": g.get("put_wall"),
        "gamma_flip": g.get("gamma_flip"),
        "net_gex_m": g.get("net_gex_m"),
        "gex_formula": g.get("gex_formula", "v1"),
        "gamma_regime": g.get("regime"),
        "top_gamma": [{"strike": r.get("strike"),
                       "net_gex_m": r.get("net_gex_m")} for r in top_gamma[:3]],
        # dealer flow pressure
        "charm_k": vc.get("total_charm_k"),
        "vanna_k": vc.get("total_vanna_k"),
        # positioning: raw volumes + OI
        "call_volume": f.get("call_volume"),
        "put_volume": f.get("put_volume"),
        "call_oi": f.get("call_oi"),
        "put_oi": f.get("put_oi"),
        "pc_volume": f.get("pc_volume"),
        "pc_oi": f.get("pc_oi"),
        # tape heat
        "hottest_strike": (top_vol[0].get("strike") if top_vol else None),
        "hottest_call_vol": (top_vol[0].get("call_vol") if top_vol else None),
        "hottest_put_vol": (top_vol[0].get("put_vol") if top_vol else None),
        "unusual_count": len(unusual),
        "unusual_notional_k": round(sum(u.get("notional_k") or 0 for u in unusual), 1),
        "top_unusual": ({"strike": top_un.get("strike"), "side": top_un.get("side"),
                         "notional_k": top_un.get("notional_k"),
                         "vol_oi": top_un.get("vol_oi")} if top_un else None),
        # volatility
        "atm_iv": iv.get("atm_call_iv"),
        "atm_put_iv": iv.get("atm_put_iv"),
        "atm_strike": iv.get("atm_strike"),
        "rr_25d": iv.get("risk_reversal_25d"),
        "smile_width": smile.get("width"),
        "smile_min_strike": smile.get("min_iv_strike"),
        # positioning analytics (blended from open-source GEX dashboards)
        "exp_move_dollars": em.get("dollars"),
        "exp_move_pct": em.get("pct"),
        "exp_move_rem_dollars": em.get("remaining_dollars"),
        "exp_move_rem_pct": em.get("remaining_pct"),
        "pin_score": p.get("pin_score"),
        "pin_magnet": p.get("pin_magnet"),
        "hedge_25bp_m": (buckets.get(25) or {}).get("notional_m"),
        "hedge_25bp_dir": (buckets.get(25) or {}).get("direction"),
        "hedge_1pct_m": (buckets.get(100) or {}).get("notional_m"),
        "hedge_1pct_dir": (buckets.get(100) or {}).get("direction"),
        "dealer_gamma_m_per_pt": p.get("dealer_gamma_notional_m_per_pt"),
        # reversal conditions (setup read, not a forecast)
        "rev_magnet": rw.get("magnet"),
        "rev_disp_dollars": rw.get("displacement_dollars"),
        "rev_stretched": rw.get("stretched"),
        "rev_conditions": rw.get("conditions") or [],
        # market events for this expiry date (FOMC, CPI, ...)
        "events": load_events().get(d.get("expiry"), []),
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    # J1: normalize the event identity up front; keep the raw feed string.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tape_db
    feed_ts = (rec.pop("ts_original")
               or datetime.now(timezone.utc).isoformat())
    rec["ts_original"] = feed_ts
    rec["ts"] = tape_db.normalize_ts(feed_ts)
    gex, gex_dict = {}, None
    try:
        spot = d.get("spot") or 0
        snap_rows = (g.get("by_strike") or [])
        gex = {str(r["strike"]): r["net_gex_m"] for r in snap_rows
               if spot and abs(r["strike"] - spot) / spot <= 0.04
               and isinstance(r.get("net_gex_m"), (int, float))}
        if gex:
            # J1: the strike map is part of the accepted event — embed it in
            # the journal record so every projection can be repaired after
            # restart from the ACCEPTED event, never the latest feed.
            # Original key spellings are preserved in projections;
            # canonical_strikes() normalizes only for comparison.
            rec["gex_m"] = {str(k): float(v) for k, v in gex.items()}
            # J1: formula fidelity — the tag follows the actual feed event,
            # never an unconditional default.
            gex_dict = {"ts": rec["ts"], "expiry": rec["expiry"],
                        "spot": spot, "gex_m": rec["gex_m"],
                        "gex_formula": rec.get("gex_formula"),
                        "gex_units": "USD millions per 1% spot move"}
    except Exception:
        pass  # heatmap snapshot is best-effort; the main record is what matters

    # J1: one duplicate/conflict decision shared with mirror/backfill.
    # The journal is the authoritative record of accepted events; the DB is
    # the fallback projection. The incoming payload is VALIDATED against the
    # accepted event — presence flags alone never decide.
    lock_fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another logger run in flight; skipping")
        return
    try:
        con = tape_db.connect()
        tape_db.init_db(con)
        ts_c, expiry = rec["ts"], rec["expiry"]
        accepted_rec = _journal_find_event(LOG_PATH, ts_c, expiry)
        if accepted_rec is not None:
            stored_core = tape_db.event_core(accepted_rec)
            accepted_gex = accepted_rec.get("gex_m")
        else:
            stored_core, db_strikes = tape_db.fetch_stored(con, ts_c, expiry)
            accepted_rec = (tape_db.rec_from_row(con, ts_c, expiry)
                            if stored_core is not None else None)
            accepted_gex = db_strikes
        incoming_core = tape_db.event_core(rec)
        incoming_gex = tape_db.canonical_strikes(gex)

        if accepted_rec is None:
            # brand-new event: write every projection
            status = tape_db.mirror_record(rec, gex, con).get("status")
            _append_line(LOG_PATH, rec)
            if gex_dict:
                _append_line(GEX_SNAP_PATH, gex_dict)
            print(f"logged | spot={rec['spot']} max_pain={rec['max_pain']} "
                  f"expiry={rec['expiry']} mirror={status}")
            return

        acc_gex = tape_db.canonical_strikes(accepted_gex)
        strikes_agree = (not incoming_gex or not acc_gex
                         or acc_gex == incoming_gex)
        decision = tape_db.classify_event(stored_core, incoming_core)

        def converge_missing():
            """Complete every projection from the ACCEPTED event only.
            Never uses the incoming payload."""
            if not tape_db.has_snapshot(con, ts_c, expiry):
                tape_db.mirror_record(accepted_rec, acc_gex, con)
            if _journal_find_event(LOG_PATH, ts_c, expiry) is None:
                _append_line(LOG_PATH, accepted_rec)
            # strike map: prefer the accepted record's original key
            # spellings; fall back to the canonical map for legacy rows.
            acc_map = (accepted_rec.get("gex_m")
                       if isinstance(accepted_rec.get("gex_m"), dict)
                       else {k: v for k, v in acc_gex.items()})
            if acc_map and _journal_find_event(GEX_SNAP_PATH, ts_c,
                                               expiry) is None:
                _append_line(GEX_SNAP_PATH, {
                    "ts": ts_c, "expiry": expiry,
                    "spot": accepted_rec.get("spot"), "gex_m": acc_map,
                    "gex_formula": accepted_rec.get("gex_formula"),
                    "gex_units": "USD millions per 1% spot move"})

        if decision == "duplicate" and strikes_agree:
            converge_missing()
            print(f"already logged | ts={ts_c}")
            return

        # Changed payload for the same identity: first repair any missing
        # projection from the ACCEPTED event (DB, journal and strike history
        # must agree), then quarantine the incoming attempt. The rejected
        # payload never becomes a projection.
        converge_missing()
        reason = ("core payload changed" if decision == "conflict"
                  else "strike map changed for identical core")
        tape_db.record_conflict(
            con, ts_c, expiry, tape_db.core_hash(stored_core),
            tape_db.core_hash(incoming_core),
            "logger: " + reason + "; accepted event stands")
        print(f"conflict quarantined | ts={ts_c} reason={reason}")
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()


def _journal_find_event(path, ts, expiry):
    """J1: full-file tolerant scan for the accepted journal record with the
    given (normalized ts, expiry). Malformed/truncated lines are skipped,
    never fatal. Returns the parsed dict of the FIRST match, or None."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tape_db
    norm = tape_db.normalize_ts
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue  # truncated tail / malformed line: skip
                if not isinstance(d, dict):
                    continue  # double-encoded or scalar line: skip
                if norm(d.get("ts")) == ts and d.get("expiry") == expiry:
                    return d
    except OSError:
        return None
    return None


def _append_line(path, obj):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj) + "\n")


if __name__ == "__main__":
    main()
