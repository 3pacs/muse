#!/usr/bin/env python3
"""
Today's ranges + pressure points, from the max-pain history log.

Usage: python3 ranges_today.py [YYYY-MM-DD]
Prints a compact readout: intraday ranges of spot/max pain/walls/flip,
and the latest pressure points (max pain, walls, flip, top gamma strikes,
hottest strike, charm/vanna extremes).
"""

import json
import os
import sys
from datetime import date

LOG_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_history.jsonl")


def load(expiry):
    recs = []
    try:
        with open(LOG_PATH) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("expiry") == expiry:
                    recs.append(r)
    except FileNotFoundError:
        pass
    return recs


def rng(recs, key):
    vals = [r[key] for r in recs if isinstance(r.get(key), (int, float))]
    if not vals:
        return None
    return min(vals), max(vals), vals[-1]


def main():
    expiry = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    recs = load(expiry)
    if not recs:
        print(f"no records for {expiry}")
        return

    n_open = sum(1 for r in recs if r.get("market_open"))
    print(f"{expiry} | {len(recs)} records ({n_open} market-open)")

    print("\nRANGES (min / max / last)")
    for label, key in [("spot", "spot"), ("max pain", "max_pain"),
                       ("call wall", "call_wall"), ("put wall", "put_wall"),
                       ("gamma flip", "gamma_flip"), ("net GEX $m", "net_gex_m"),
                       ("charm $k", "charm_k"), ("vanna $k", "vanna_k"),
                       ("ATM IV", "atm_iv"), ("P/C vol", "pc_volume"),
                       ("exp move $", "exp_move_rem_dollars"),
                       ("exp move %", "exp_move_rem_pct"),
                       ("pin score", "pin_score"),
                       ("hedge +-1% $m", "hedge_1pct_m")]:
        v = rng(recs, key)
        if v:
            lo, hi, last = v
            print(f"  {label:12s} {lo:>14,.2f} {hi:>14,.2f} {last:>14,.2f}")

    last = recs[-1]
    ev = last.get("events") or []
    if ev:
        print(f"\nEVENTS TODAY: {', '.join(ev)}")
    print("\nPRESSURE POINTS (latest)")
    print(f"  max pain      {last.get('max_pain')}")
    print(f"  call wall     {last.get('call_wall')}")
    print(f"  put wall      {last.get('put_wall')}")
    print(f"  gamma flip    {last.get('gamma_flip')}  ({last.get('gamma_regime')})")
    emd, emp = last.get("exp_move_rem_dollars"), last.get("exp_move_rem_pct")
    if emd is not None:
        print(f"  exp move      ±${emd:,.2f} (±{emp:.2f}%) remaining")
    ps, pm = last.get("pin_score"), last.get("pin_magnet")
    if ps is not None:
        print(f"  pin score     {ps:.0f}/100  (magnet {pm})")
    h25, h25d = last.get("hedge_25bp_m"), last.get("hedge_25bp_dir")
    h100, h100d = last.get("hedge_1pct_m"), last.get("hedge_1pct_dir")
    if h25 is not None and h100 is not None:
        print(f"  hedge flow    ±25bp: {h25d} ${abs(h25):,.0f}m | "
              f"±1%: {h100d} ${abs(h100):,.0f}m")
    tg = last.get("top_gamma") or []
    print("  top gamma     " + ", ".join(
        f"{t.get('strike')} (${t.get('net_gex_m') or 0:,.0f}m)" for t in tg))
    print(f"  hottest tape  {last.get('hottest_strike')}")
    tu = last.get("top_unusual")
    if tu:
        print(f"  big print     {tu.get('side')} {tu.get('strike')} "
              f"${(tu.get('notional_k') or 0)/1000:,.1f}m notional, {tu.get('vol_oi')}x OI")
    print(f"  unusual count {last.get('unusual_count')}")
    print(f"  spot vs pain  {((last.get('spot') or 0) - (last.get('max_pain') or 0)):+.2f}")


if __name__ == "__main__":
    main()
