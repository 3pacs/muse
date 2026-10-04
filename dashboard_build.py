#!/usr/bin/env python3
"""
Builds dashboard_data.json for the 0DTE web dashboard.

Reads the max-pain history log + per-strike GEX snapshots for a date and
emits one compact JSON the dashboard renders: latest snapshot, intraday
ranges, hedge buckets, pin score, event tags, and a strike x time GEX
heatmap matrix. Missing fields degrade gracefully (None / empty).

Usage: python3 dashboard_build.py [YYYY-MM-DD]  (default: today)
Output: ~/workspace/goals/0dte-tape-alert-watch/hidden_files/dashboard_data.json
"""

import json
import os
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

HIDDEN = os.path.expanduser("~/workspace/goals/0dte-tape-alert-watch/hidden_files")
LOG_PATH = os.path.join(HIDDEN, "maxpain_history.jsonl")
GEX_PATH = os.path.join(HIDDEN, "gex_history.jsonl")
OUT_PATH = os.path.join(HIDDEN, "dashboard_data.json")
PT = ZoneInfo("America/Los_Angeles")


def market_open_now_pt():
    pt = datetime.now(PT)
    if pt.weekday() >= 5:
        return False
    mins = pt.hour * 60 + pt.minute
    return 6 * 60 + 30 <= mins < 13 * 60


def load_jsonl(path):
    recs = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return recs


def rng(recs, key):
    vals = [r[key] for r in recs if isinstance(r.get(key), (int, float))]
    if not vals:
        return None
    return {"lo": round(min(vals), 2), "hi": round(max(vals), 2),
            "last": round(vals[-1], 2)}


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    if "--force" not in sys.argv and not market_open_now_pt():
        print("market closed — skipping")
        return
    recs = [r for r in load_jsonl(LOG_PATH) if r.get("expiry") == day]
    snaps = [s for s in load_jsonl(GEX_PATH) if s.get("expiry") == day]

    data = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": {
            "records": len(recs),
            "market_open": sum(1 for r in recs if r.get("market_open")),
            "snapshots": len(snaps),
        },
        "latest": None, "ranges": [], "hedge_buckets": [],
        "heatmap": {"strikes": [], "times": [], "values": []},
        "data_quality": [],
    }

    if not recs:
        data["data_quality"].append(f"no records for {day}")
        json.dump(data, open(OUT_PATH, "w"))
        print(f"wrote {OUT_PATH} (empty)")
        return

    last = recs[-1]
    data["latest"] = {
        "spot": last.get("spot"),
        "max_pain": last.get("max_pain"),
        "call_wall": last.get("call_wall"),
        "put_wall": last.get("put_wall"),
        "gamma_flip": last.get("gamma_flip"),
        "regime": last.get("gamma_regime"),
        "expected_move": {
            "dollars": last.get("exp_move_rem_dollars"),
            "pct": last.get("exp_move_rem_pct"),
        },
        "pin_score": last.get("pin_score"),
        "pin_magnet": last.get("pin_magnet"),
        "hedge_25bp": {"notional_m": last.get("hedge_25bp_m"),
                       "direction": last.get("hedge_25bp_dir")},
        "hedge_1pct": {"notional_m": last.get("hedge_1pct_m"),
                       "direction": last.get("hedge_1pct_dir")},
        "atm_iv": last.get("atm_iv"),
        "pc_volume": last.get("pc_volume"),
        "events": last.get("events") or [],
        "top_gamma": [{"strike": t.get("strike")} for t in (last.get("top_gamma") or [])],
        "reversal": {
            "magnet": last.get("rev_magnet"),
            "displacement_dollars": last.get("rev_disp_dollars"),
            "stretched": last.get("rev_stretched"),
            "conditions": last.get("rev_conditions") or [],
        },
        "spot_vs_pain": (round(last["spot"] - last["max_pain"], 2)
                         if isinstance(last.get("spot"), (int, float))
                         and isinstance(last.get("max_pain"), (int, float)) else None),
    }

    for label, key in [("Spot", "spot"), ("Max pain", "max_pain"),
                       ("Call wall", "call_wall"), ("Put wall", "put_wall"),
                       ("Gamma flip", "gamma_flip"), ("ATM IV", "atm_iv"),
                       ("P/C volume", "pc_volume"),
                       ("Expected move $", "exp_move_rem_dollars"),
                       ("Expected move %", "exp_move_rem_pct"),
                       ("Pin score", "pin_score"),
                       ("Hedge ±1% $m", "hedge_1pct_m")]:
        v = rng(recs, key)
        if v:
            data["ranges"].append({"label": label, **v})

    # hedge buckets: rebuild full ladder from latest record's two anchor points
    # (25bp and 100bp); intermediate buckets scale linearly with shock size
    h25, h100 = last.get("hedge_25bp_m"), last.get("hedge_1pct_m")
    if isinstance(h25, (int, float)) and isinstance(h100, (int, float)):
        per_bp_25 = h25 / 25.0
        per_bp_100 = h100 / 100.0
        per_bp = (per_bp_25 + per_bp_100) / 2.0
        data["hedge_buckets"] = [
            {"shock": "±10bp", "notional_m": round(per_bp * 10, 1),
             "direction": last.get("hedge_25bp_dir")},
            {"shock": "±25bp", "notional_m": round(h25, 1),
             "direction": last.get("hedge_25bp_dir")},
            {"shock": "±50bp", "notional_m": round(per_bp * 50, 1),
             "direction": last.get("hedge_1pct_dir")},
            {"shock": "±1%", "notional_m": round(h100, 1),
             "direction": last.get("hedge_1pct_dir")},
        ]

    # heatmap: strike x time matrix of per-strike net GEX ($m)
    if snaps:
        strikes = sorted({float(k) for s in snaps for k in s.get("gex_m", {})})
        # downsample time to <= 48 columns
        step = max(1, len(snaps) // 48)
        cols = snaps[::step]
        times, values = [], []
        for s in cols:
            gm = s.get("gex_m", {})
            times.append(s["ts"][11:16])
            values.append([round(gm.get(str(k), 0.0), 1) for k in strikes])
        data["heatmap"] = {"strikes": strikes, "times": times, "values": values}
    else:
        data["data_quality"].append(
            "GEX heatmap starts collecting Monday — per-strike snapshots "
            "were added after this session")

    # honesty notes
    n_rtd_note = ("3 live RTD strikes + Nasdaq-delayed wings (~15 min); "
                  "walls/flip can flicker on mixed snapshots")
    data["data_quality"].append(n_rtd_note)
    data["data_quality"].append(
        "GEX/charm/vanna dollar magnitudes swing on feed mixing — "
        "treat levels as signal, dollar sizes as rough")
    data["data_quality"].append(
        "Dealer positioning assumes long calls / short puts (standard GEX "
        "convention) — a prior, not observed truth")

    json.dump(data, open(OUT_PATH, "w"))
    print(f"wrote {OUT_PATH}: {len(recs)} records, "
          f"{len(data['heatmap']['times'])} heatmap cols")


if __name__ == "__main__":
    main()
