#!/usr/bin/env python3
"""
0DTE max-pain + pressure-point tracker.

Polls the interpreter's /feed/all and prints ALERT lines only for:
  - maxpain_open     first reading of the day (the anchor)
  - maxpain_moved    max pain repriced to a new strike
  - maxpain_reversed max pain drift changed direction (30m lookback, >=$1)
  - wall_moved       call or put wall repriced
  - flip_moved       gamma flip moved >= $0.50
  - pin_cross        spot crossed max pain (magnet touch)

Everything else stays quiet. Anik dropped the noisy firehose (2026-10-01):
track max pain, and ping him when it or the pressure points move or
change direction.

Usage: python3 watcher.py
  Prints "ALERT <key> | <message>" lines, or "QUIET" / "MARKET_CLOSED".

State: watcher_state.json (per-day history).
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FEED_URL = "http://localhost:8787/feed/all"
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watcher_state.json")
PT = ZoneInfo("America/Los_Angeles")


def market_open_now():
    now = datetime.now(timezone.utc).astimezone(PT)
    if now.weekday() >= 5:
        return False
    return 6 * 60 + 30 <= now.hour * 60 + now.minute < 13 * 60


def today_key():
    return datetime.now(timezone.utc).astimezone(PT).strftime("%Y-%m-%d")


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(s):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE_PATH)


def fetch():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "stepdad-0dte-maxpain/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main():
    if not market_open_now():
        print("MARKET_CLOSED")
        return
    try:
        d = fetch()
    except Exception as e:
        print(f"FEED_DOWN | {e}")
        return
    if d.get("status") != "ok":
        print(f"FEED_ERROR | {d.get('error', 'unknown')}")
        return

    spot = d.get("spot")
    g = d.get("gamma") or {}
    mp = g.get("max_pain")
    cw = g.get("call_wall")
    pw = g.get("put_wall")
    flip = g.get("gamma_flip")
    if mp is None or spot is None:
        print("FEED_ERROR | max_pain missing from feed")
        return

    state = load_state()
    day = today_key()
    rec = state.get(day) or {"open_mp": None, "last_mp": None,
                             "last_spot_vs_mp": None,
                             "last_cw": None, "last_pw": None,
                             "last_cw_alert_t": 0, "last_pw_alert_t": 0,
                             "cw_alert_hist": [], "pw_alert_hist": [],
                             "last_flip_alert": None,
                             "last_direction": None, "last_dir_alert_t": 0,
                             "readings": []}
    alerts = []
    now_t = time.time()

    def rel(s):
        return f"{s - mp:+.2f} vs max pain" if mp else ""

    if rec["open_mp"] is None:
        rec["open_mp"] = mp
        alerts.append(f"ALERT maxpain_open | max pain at open {mp:.0f} (spot {spot:.2f}, {rel(spot)})")

    prev_mp = rec["last_mp"]
    if prev_mp is not None and mp != prev_mp:
        alerts.append(f"ALERT maxpain_moved | max pain {prev_mp:.0f} -> {mp:.0f} "
                      f"(spot {spot:.2f}, {rel(spot)})")

    # pressure-point repricing: walls + gamma flip.
    # Anti-flicker: a wall oscillating between two strikes on data refresh
    # is not a move. Alert only when the wall reaches a level not seen in
    # its last few alerts, with a 15-min per-side cooldown as backstop.
    # Genuine relocations (new levels) always get through.
    if cw is not None and rec["last_cw"] is not None and cw != rec["last_cw"]:
        seen = rec.get("cw_alert_hist", [])
        if cw not in seen and now_t - rec.get("last_cw_alert_t", 0) >= 900:
            alerts.append(f"ALERT wall_moved | call wall {rec['last_cw']:.0f} -> {cw:.0f}")
            rec["last_cw_alert_t"] = now_t
            rec["cw_alert_hist"] = ([cw] + seen)[:4]
    if pw is not None and rec["last_pw"] is not None and pw != rec["last_pw"]:
        seen = rec.get("pw_alert_hist", [])
        if pw not in seen and now_t - rec.get("last_pw_alert_t", 0) >= 900:
            alerts.append(f"ALERT wall_moved | put wall {rec['last_pw']:.0f} -> {pw:.0f}")
            rec["last_pw_alert_t"] = now_t
            rec["pw_alert_hist"] = ([pw] + seen)[:4]
    if flip is not None:
        lf = rec.get("last_flip_alert")
        band = int(flip)  # $1 band
        seen_bands = rec.get("flip_band_hist", [])
        if lf is not None and abs(flip - lf) >= 1.00 and band not in seen_bands:
            alerts.append(f"ALERT flip_moved | gamma flip {lf:.2f} -> {flip:.2f}")
            rec["last_flip_alert"] = flip
            rec["flip_band_hist"] = ([band] + seen_bands)[:3]
        elif lf is None:
            rec["last_flip_alert"] = flip
            rec["flip_band_hist"] = [band]

    # direction change: max-pain drift over a ~30m lookback
    rec["readings"].append({"t": now_t, "mp": mp, "spot": round(spot, 2)})
    rec["readings"] = rec["readings"][-500:]
    hist = rec["readings"]
    if len(hist) >= 15:
        drift = mp - hist[-15]["mp"]
        direction = "up" if drift >= 1.0 else "down" if drift <= -1.0 else None
        prev_dir = rec["last_direction"]
        if direction and prev_dir and direction != prev_dir \
                and now_t - rec["last_dir_alert_t"] >= 1800:
            alerts.append(f"ALERT maxpain_reversed | max pain changed direction: "
                          f"was drifting {prev_dir}, now {direction} "
                          f"({drift:+.0f} over ~30m, now {mp:.0f})")
            rec["last_dir_alert_t"] = now_t
            rec["last_direction"] = direction
        elif direction and direction != prev_dir:
            rec["last_direction"] = direction

    prev_side = rec["last_spot_vs_mp"]
    side = "above" if spot > mp else "below" if spot < mp else "at"
    if prev_side is not None and side != prev_side and side in ("above", "below"):
        alerts.append(f"ALERT pin_cross | spot crossed max pain {mp:.0f} -> {side} it ({spot:.2f})")

    rec["last_mp"] = mp
    rec["last_cw"] = cw
    rec["last_pw"] = pw
    rec["last_spot_vs_mp"] = side
    state[day] = rec
    # keep a week of days
    for k in [k for k in state if k != day and k < day]:
        pass
    keys = sorted(state.keys())
    for k in keys[:-7]:
        del state[k]
    save_state(state)

    print("\n".join(alerts) if alerts else "QUIET")


if __name__ == "__main__":
    main()
