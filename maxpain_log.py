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
        # R4: event identity comes from the FEED's own timestamps, not the
        # logger clock. Replaying the same feed must converge to one record;
        # the receipt clock is metadata, never identity.
        "ts": d.get("updated_at") or d.get("quote_as_of")
              or datetime.now(timezone.utc).isoformat(),
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
    gex, gex_line = {}, None
    try:
        spot = d.get("spot") or 0
        snap_rows = (g.get("by_strike") or [])
        gex = {str(r["strike"]): r["net_gex_m"] for r in snap_rows
               if spot and abs(r["strike"] - spot) / spot <= 0.04
               and isinstance(r.get("net_gex_m"), (int, float))}
        if gex:
            # R6: every strike-history event carries its formula/units tag.
            gex_line = json.dumps({"ts": rec["ts"], "expiry": rec["expiry"],
                                   "spot": spot, "gex_m": gex,
                                   "gex_formula": "v2",
                                   "gex_units": "USD millions per 1% spot move"})
    except Exception:
        pass  # heatmap snapshot is best-effort; the main record is what matters

    # F10/R3/R4: single-flight + reconcile against ALL projections.
    # The main JSONL is the declared authoritative journal; a run converges
    # every projection (DB snapshot, main JSONL, strike JSONL) independently,
    # so a crash between appends is repaired by the next run instead of
    # stranding a permanently incomplete strike history (R3).
    lock_fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another logger run in flight; skipping")
        return
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tape_db
        con = tape_db.connect()
        tape_db.init_db(con)
        in_db = tape_db.has_snapshot(con, rec["ts"], rec["expiry"])
        in_jsonl = _jsonl_has_ts(LOG_PATH, rec["ts"])
        in_gex = _jsonl_has_ts(GEX_SNAP_PATH, rec["ts"]) if gex_line else True
        if in_db and in_jsonl and in_gex:
            print(f"already logged | ts={rec['ts']}")
            return
        mirror_status = "skipped"
        if not in_db:
            mirror_status = tape_db.mirror_record(rec, gex or {}, con).get("status")
        if not in_jsonl:
            with open(LOG_PATH, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
        if gex_line and not in_gex:
            with open(GEX_SNAP_PATH, "a") as fh:
                fh.write(gex_line + "\n")
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()

    print(f"logged | spot={rec['spot']} max_pain={rec['max_pain']} "
          f"expiry={rec['expiry']} mirror={mirror_status}")


def _jsonl_has_ts(path, ts):
    """Tail-scan for a record ts (F10 reconcile)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            tail = fh.read().decode("utf-8", "replace")
        needle = f'"ts": "{ts}"'
        return needle in tail
    except OSError:
        return False


if __name__ == "__main__":
    main()
