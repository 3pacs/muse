#!/usr/bin/env python3
"""Indicator hit/switch tracker for SPY 1-min bars.

Computes the classic TradingView/thinkorswim indicator set (RSI, Stochastic,
MACD, VWAP, volume) on 1-min and 5-min SPY bars, detects "hit" and "switch"
events, detects multi-indicator STACKS (the pattern), logs every event to
tape.db (indicator_events) + indicator_events.jsonl, and scores forward
outcomes (+5/+15/+30 min, MFE/MAE) so patterns can be evaluated on data.

Modes:
  --backfill YYYY-MM-DD   compute a full past session, store, print summary
  --live                  compute today so far, store NEW events, print new
                          STACK lines (and EVENT lines for singles)
  --report                aggregate hit-rate stats from stored events

Bars: Yahoo chart API 1-min (near-real-time for SPY). Session 09:30-16:00 ET.
Indicators use standard definitions (Wilder RSI, SMA-smoothed Stochastic,
EMA MACD) matching what TradingView shows by default.
"""
import argparse, json, math, sqlite3, sys, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DB_PATH = "/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db"
JSONL_PATH = "/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files/indicator_events.jsonl"

# ---------------- bars ----------------

def _fetch_bars_once(symbol, day_et, start_hm=(9, 30)):
    rng = "7d" if day_et != datetime.now(ET).date().isoformat() else "1d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range={rng}&includePrePost=false"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        d = json.load(resp)
    r = d["chart"]["result"][0]
    ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        dt = datetime.fromtimestamp(t, timezone.utc)
        et = dt.astimezone(ET)
        if et.date().isoformat() != day_et:
            continue
        if (et.hour, et.minute) < start_hm or (et.hour, et.minute) >= (16, 0):
            continue
        bars.append((dt, q["open"][i], q["high"][i], q["low"][i], c, q["volume"][i] or 0))
    return bars

def _phantom_share(bars):
    """Fraction of session volume sitting in implausible mid-session bars
    (>5M shares in one minute, excluding the 09:30 open and 15:59 close
    prints). Yahoo intermittently serves a corrupted variant of the same
    session where a few bars carry 10-30M shares (verified 2026-10-14:
    variant totals 151M vs the true 62M, prices identical, volumes wrong).
    Prices are trustworthy in both variants; volume-derived math is not."""
    tot = sum(b[5] for b in bars)
    if tot <= 0:
        return 1.0
    ph = 0
    for b in bars:
        et = b[0].astimezone(ET)
        if b[5] > 5_000_000 and (et.hour, et.minute) not in ((9, 30), (15, 59)):
            ph += b[5]
    return ph / tot

def fetch_bars(day_et=None, symbol="SPY", start_hm=(9, 30), equity=True):
    """Return list of (ts_utc, o, h, l, c, v) 1-min bars for one ET session
    of `symbol` (Yahoo path form, e.g. 'SPY', 'QQQ', '%5EVIX', '%5ETNX').
    For equities, fetches up to 3 times and keeps the variant with the
    least phantom volume; any remaining >5M mid-session bars have their
    volume replaced with the trailing 30-bar median so VWAP/ignition math
    stays sane. Index symbols have no volume; fetched once, unguarded."""
    if day_et is None:
        day_et = datetime.now(ET).date().isoformat()
    if not equity:
        try:
            return _fetch_bars_once(symbol, day_et, start_hm)
        except Exception:
            return []
    best = None; best_ph = 2.0
    for _ in range(3):
        try:
            cand = _fetch_bars_once(symbol, day_et, start_hm)
        except Exception:
            continue
        if not cand:
            continue
        ph = _phantom_share(cand)
        if ph < best_ph:
            best, best_ph = cand, ph
        if ph < 0.02:
            break
    if not best:
        return []
    bars = list(best)
    vols = [b[5] for b in bars]
    for i, b in enumerate(bars):
        et = b[0].astimezone(ET)
        if b[5] > 5_000_000 and (et.hour, et.minute) not in ((9, 30), (15, 59)):
            prior = sorted(vols[max(0, i - 30):i])
            med = prior[len(prior) // 2] if prior else 0
            bars[i] = (b[0], b[1], b[2], b[3], b[4], med)
    return bars

def agg5(bars):
    """Aggregate 1-min bars into CLOCK-aligned 5-min bars (09:30, 09:35, ...
    ET). Bucketing by clock, not by consecutive chunks, so a missing minute
    in the feed cannot shift every later bar's boundary. Each output bar is
    (start_ts, o, h, l, c, v, last_1m_idx)."""
    buckets = {}
    order = []
    for idx, b in enumerate(bars):
        et = b[0].astimezone(ET)
        start = et.replace(minute=(et.minute // 5) * 5, second=0, microsecond=0)
        key = start.astimezone(timezone.utc)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((idx, b))
    out = []
    for key in order:
        g = buckets[key]
        out.append((g[0][1][0], g[0][1][1], max(x[1][2] for x in g),
                    min(x[1][3] for x in g), g[-1][1][4],
                    sum(x[1][5] for x in g), g[-1][0]))
    return out

# ---------------- indicators ----------------

def rsi_wilder(closes, n=14):
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    ag = sum(gains[:n]) / n; al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
        out[i + 1] = 100 - 100 / (1 + (ag / al if al > 0 else 999.0))
    return out

def ema(vals, n):
    k = 2 / (n + 1); out = [vals[0]]
    for v in vals[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out

def sma(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        w = vals[i - n + 1:i + 1]
        if all(v is not None for v in w):
            out[i] = sum(w) / n
    return out

def stoch_k(bars, n=14):
    raw = [None] * len(bars)
    for i in range(n - 1, len(bars)):
        w = bars[i - n + 1:i + 1]
        hh = max(x[2] for x in w); ll = min(x[3] for x in w)
        raw[i] = 100 * (bars[i][4] - ll) / (hh - ll) if hh > ll else 50.0
    return raw

# ---------------- event detection ----------------

CORE_FOR_STACK = {"rsi_divergence", "stoch_cross"}

def detect_events(bars, symbol="SPY", equity=True):
    """Return list of event dicts: {ts_close (utc dt of bar close), type,
    direction ('bull'/'bear'), spot, detail{}, symbol, score_symbol}.
    For non-equity symbols (indices), volume-based events are skipped."""
    b5 = agg5(bars)
    if len(b5) < 30:
        return []
    c1 = [b[4] for b in bars]; c5 = [b[4] for b in b5]
    rsi1 = rsi_wilder(c1); rsi5 = rsi_wilder(c5)
    rawk = stoch_k(b5); kk = sma(rawk, 3); dd = sma(kk, 3)
    macd_line = [a - b for a, b in zip(ema(c5, 12), ema(c5, 26))]
    sig = ema(macd_line, 9); hist = [a - b for a, b in zip(macd_line, sig)]
    # VWAP from 1-min typical price, mapped to each 5-min bar close
    cum_pv = 0.0; cum_v = 0; vwap_1m = []
    for b in bars:
        tp = (b[2] + b[3] + b[4]) / 3
        cum_pv += tp * b[5]; cum_v += b[5]
        vwap_1m.append(cum_pv / cum_v if cum_v else tp)

    events = []
    def close_ts_5(i):  # close time of 5-min bar i
        return b5[i][0] + timedelta(minutes=5)
    def close_ts_1(i):
        return bars[i][0] + timedelta(minutes=1)

    # --- swing tracking on 5-min (1-bar confirmation each side) ---
    # Structure events compare against the LEG EXTREME: the min/max swing of
    # the trailing 24 bars (2h), at least 3 bars old -- not the adjacent
    # micro-swing (chop manufactures those all day).
    swing_lows = []   # (bar_idx, low, rsi5)
    swing_highs = []  # (bar_idx, high, rsi5)
    for i in range(1, len(b5) - 1):
        lo, hi = b5[i][3], b5[i][2]
        if lo < b5[i - 1][3] and lo <= b5[i + 1][3]:
            prior = [s for s in swing_lows if i - 24 <= s[0] <= i - 3]
            if prior:
                pi, plow, _ = min(prior, key=lambda s: s[1])
                if lo > plow + 0.10:
                    events.append(dict(ts=close_ts_5(i + 1), type="higher_low",
                                       direction="bull", spot=b5[i + 1][4],
                                       detail={"swing_low": lo, "leg_low": plow}))
            swing_lows.append((i, lo, rsi5[i]))
        if hi > b5[i - 1][2] and hi >= b5[i + 1][2]:
            prior = [s for s in swing_highs if i - 24 <= s[0] <= i - 3]
            if prior:
                pi, phigh, _ = max(prior, key=lambda s: s[1])
                if hi < phigh - 0.10:
                    events.append(dict(ts=close_ts_5(i + 1), type="lower_high",
                                       direction="bear", spot=b5[i + 1][4],
                                       detail={"swing_high": hi, "leg_high": phigh}))
            swing_highs.append((i, hi, rsi5[i]))

    # --- per-bar 5-min events ---
    last_div_ref_low = None; last_div_ref_high = None
    stretch_armed_dn = True; stretch_armed_up = True
    rsi_extreme_armed_dn = True; rsi_extreme_armed_up = True
    for i in range(1, len(b5)):
        ts = close_ts_5(i); spot = b5[i][4]
        # stochastic crosses
        if None not in (kk[i], dd[i], kk[i - 1], dd[i - 1]):
            if kk[i - 1] <= dd[i - 1] and kk[i] > dd[i] and kk[i] < 50:
                events.append(dict(ts=ts, type="stoch_cross", direction="bull", spot=spot,
                                   detail={"k": round(kk[i], 1), "d": round(dd[i], 1)}))
            if kk[i - 1] >= dd[i - 1] and kk[i] < dd[i] and kk[i] > 50:
                events.append(dict(ts=ts, type="stoch_cross", direction="bear", spot=spot,
                                   detail={"k": round(kk[i], 1), "d": round(dd[i], 1)}))
        # MACD hist flip
        if hist[i - 1] <= 0 < hist[i]:
            events.append(dict(ts=ts, type="macd_flip", direction="bull", spot=spot,
                               detail={"hist": round(hist[i], 3)}))
        if hist[i - 1] >= 0 > hist[i]:
            events.append(dict(ts=ts, type="macd_flip", direction="bear", spot=spot,
                               detail={"hist": round(hist[i], 3)}))
        # MACD hist expansion: 3 consecutive same-direction increases in |hist|
        if i >= 3:
            h = hist[i - 3:i + 1]
            if h[0] > 0 and h[1] > h[0] and h[2] > h[1] and h[3] > h[2]:
                events.append(dict(ts=ts, type="macd_expand", direction="bull", spot=spot,
                                   detail={"hist": round(hist[i], 3)}))
            if h[0] < 0 and h[1] < h[0] and h[2] < h[1] and h[3] < h[2]:
                events.append(dict(ts=ts, type="macd_expand", direction="bear", spot=spot,
                                   detail={"hist": round(hist[i], 3)}))
        # RSI5 extreme HIT (reversal context): cross into <=30 / >=70,
        # re-arm at 40 / 60. Direction = expected tradable move.
        if rsi5[i] is not None and rsi5[i - 1] is not None:
            if rsi5[i - 1] > 30 >= rsi5[i] and rsi_extreme_armed_dn:
                events.append(dict(ts=ts, type="rsi_extreme", direction="bull", spot=spot,
                                   detail={"rsi5": round(rsi5[i], 1)}))
                rsi_extreme_armed_dn = False
            if rsi5[i] > 40:
                rsi_extreme_armed_dn = True
            if rsi5[i - 1] < 70 <= rsi5[i] and rsi_extreme_armed_up:
                events.append(dict(ts=ts, type="rsi_extreme", direction="bear", spot=spot,
                                   detail={"rsi5": round(rsi5[i], 1)}))
                rsi_extreme_armed_up = False
            if rsi5[i] < 60:
                rsi_extreme_armed_up = True
        # VWAP stretch (reversal context): fire once per threshold crossing
        dev = spot - vwap_1m[b5[i][6]] if equity else 0.0
        if dev <= -3.00 and stretch_armed_dn:
            events.append(dict(ts=ts, type="vwap_stretch", direction="bull", spot=spot,
                               detail={"vwap_dev": round(dev, 2)}))
            stretch_armed_dn = False
        if dev > -1.50:
            stretch_armed_dn = True
        if dev >= 3.00 and stretch_armed_up:
            events.append(dict(ts=ts, type="vwap_stretch", direction="bear", spot=spot,
                               detail={"vwap_dev": round(dev, 2)}))
            stretch_armed_up = False
        if dev < 1.50:
            stretch_armed_up = True
        # RSI divergence vs the LEG EXTREME swing (min low / max high of the
        # trailing 24 bars, >=3 bars old), two-sided retest band +/-0.75.
        # Live-readable at bar close; locked per reference swing.
        if rsi5[i] is not None:
            prior_lo = [s for s in swing_lows if i - 24 <= s[0] <= i - 3]
            if prior_lo:
                pi, plow, prsi = min(prior_lo, key=lambda s: s[1])
                if (last_div_ref_low != pi and prsi is not None
                        and plow - 0.75 <= b5[i][3] <= plow + 0.75
                        and rsi5[i] >= prsi + 5):
                    events.append(dict(ts=ts, type="rsi_divergence", direction="bull", spot=spot,
                                       detail={"price_low": b5[i][3], "leg_low": plow,
                                               "rsi_now": round(rsi5[i], 1), "rsi_at_leg": round(prsi, 1),
                                               "leg_age_min": (i - pi) * 5,
                                               "leg_is_session_extreme": plow <= min(x[3] for x in b5[:i + 1]) + 1e-9,
                                               "vwap_dev": round(spot - vwap_1m[b5[i][6]], 2)}))
                    last_div_ref_low = pi
            prior_hi = [s for s in swing_highs if i - 24 <= s[0] <= i - 3]
            if prior_hi:
                pi, phigh, prsi = max(prior_hi, key=lambda s: s[1])
                if (last_div_ref_high != pi and prsi is not None
                        and phigh - 0.75 <= b5[i][2] <= phigh + 0.75
                        and rsi5[i] <= prsi - 5):
                    events.append(dict(ts=ts, type="rsi_divergence", direction="bear", spot=spot,
                                       detail={"price_high": b5[i][2], "leg_high": phigh,
                                               "rsi_now": round(rsi5[i], 1), "rsi_at_leg": round(prsi, 1),
                                               "leg_age_min": (i - pi) * 5,
                                               "leg_is_session_extreme": phigh >= max(x[2] for x in b5[:i + 1]) - 1e-9,
                                               "vwap_dev": round(spot - vwap_1m[b5[i][6]], 2)}))
                    last_div_ref_high = pi

    # --- 1-min events: RSI extreme crosses (gated: RSI1 must spend >=5
    # consecutive minutes beyond the extreme first, else every micro-bounce
    # in a trend fires it) + volume ignition ---
    mins_below = 0; mins_above = 0
    for i in range(1, len(bars)):
        if rsi1[i] is not None:
            if rsi1[i] < 30:
                mins_below += 1
            elif rsi1[i] > 35:
                mins_below = 0
            if rsi1[i] > 70:
                mins_above += 1
            elif rsi1[i] < 65:
                mins_above = 0
        if rsi1[i] is not None and rsi1[i - 1] is not None:
            if rsi1[i - 1] <= 30 < rsi1[i] and mins_below >= 5:
                events.append(dict(ts=close_ts_1(i), type="rsi1_reversal", direction="bull",
                                   spot=bars[i][4], detail={"rsi1": round(rsi1[i], 1),
                                                             "mins_below_30": mins_below}))
                mins_below = 0
            if rsi1[i - 1] >= 70 > rsi1[i] and mins_above >= 5:
                events.append(dict(ts=close_ts_1(i), type="rsi1_reversal", direction="bear",
                                   spot=bars[i][4], detail={"rsi1": round(rsi1[i], 1),
                                                             "mins_above_70": mins_above}))
                mins_above = 0
        if i >= 30:
            et = bars[i][0].astimezone(ET)
            if (9, 31) <= (et.hour, et.minute) < (15, 45):
                vols = sorted(bars[j][5] for j in range(i - 30, i))
                med = vols[len(vols) // 2]
                # relative ignition OR absolute MEGA print (Anik 2026-10-14:
                # the 1.07M-share capitulation minute at the low and the
                # 1.09M ignition minute at the takeoff are the markers --
                # on heavy days the relative rule alone can miss them
                # because the trailing median is itself huge).
                mega_floor = {"SPY": 800000, "QQQ": 400000}.get(symbol, 10 ** 18)
                rel = med > 0 and bars[i][5] >= 6 * med and bars[i][5] >= 300000
                # mega ALSO requires >=4x the trailing median: raw volume
                # pours in toward the close, so a big absolute minute late
                # in the day is not by itself abnormal (Anik 2026-10-14).
                mega = bars[i][5] >= mega_floor and med > 0 and bars[i][5] >= 4 * med
                if equity and (rel or mega):
                    direction = "bull" if bars[i][4] >= bars[i][1] else "bear"
                    sess_low = min(b[3] for b in bars[:i + 1])
                    sess_high = max(b[2] for b in bars[:i + 1])
                    events.append(dict(ts=close_ts_1(i), type="vol_ignition", direction=direction,
                                       spot=bars[i][4],
                                       detail={"vol": int(bars[i][5]), "median30": int(med),
                                               "mult": round(bars[i][5] / med, 1) if med else None,
                                               "mega": bool(mega),
                                               "at_lows": bool(bars[i][3] <= sess_low * 1.0012),
                                               "at_highs": bool(bars[i][2] >= sess_high * 0.9988)}))

    events.sort(key=lambda e: e["ts"])

    # --- stacks (the pattern). Two paths:
    #   A) >=3 same-direction events within 15 min incl. >=1 core type
    #      (rsi1_reversal counts at most once per window -- it chatters).
    #   B) divergence + structure (higher_low/lower_high) within 20 min:
    #      the double-bottom/top pattern, fires at the second member.
    # 30-min suppression per direction after a stack fires.
    stacks = []
    last_stack = {}  # (direction, path) -> ts ; suppression is per-path
    last_stack_any = {}  # direction -> ts ; no second-path refire within 10 min
    struct_type = {"bull": "higher_low", "bear": "lower_high"}
    for idx, e in enumerate(events):
        d = e["direction"]
        window = [x for x in events[:idx + 1]
                  if x["direction"] == d and 0 <= (e["ts"] - x["ts"]).total_seconds() <= 900]
        seen_rsi1 = False; members = []
        for x in window:
            if x["type"] == "rsi1_reversal":
                if seen_rsi1:
                    continue
                seen_rsi1 = True
            members.append(x)
        distinct_types = {x["type"] for x in members}
        path_a = len(distinct_types) >= 3 and bool(distinct_types & CORE_FOR_STACK)
        path_b = False
        if e["type"] in ("rsi_divergence", struct_type[d]):
            wide = [x for x in events[:idx + 1]
                    if x["direction"] == d and 0 <= (e["ts"] - x["ts"]).total_seconds() <= 1200]
            wtypes = {x["type"] for x in wide}
            if "rsi_divergence" in wtypes and struct_type[d] in wtypes:
                path_b = True
                members = wide
        prev_any = last_stack_any.get(d)
        if prev_any and (e["ts"] - prev_any).total_seconds() < 600:
            continue  # a stack for this direction fired <10 min ago; no refire
        for path, ok in (("B", path_b), ("A", path_a)):
            if not ok:
                continue
            prev = last_stack.get((d, path))
            if prev and (e["ts"] - prev).total_seconds() < 1800:
                continue
            stacks.append(dict(ts=e["ts"], type="STACK", direction=d, spot=e["spot"],
                               detail={"members": [f"{x['type']}@{x['ts'].astimezone(ET).strftime('%H:%M')}" for x in members],
                                       "n": len(members), "path": path}))
            last_stack[(d, path)] = e["ts"]
            last_stack_any[d] = e["ts"]
            break
    events.extend(stacks)
    events.sort(key=lambda e: e["ts"])
    for e in events:
        e.setdefault("symbol", symbol)
        e.setdefault("score_symbol", symbol)
    return events

# ---------------- scoring ----------------

def score_event(ev, bars):
    """Forward returns (points, direction-signed) using 1-min closes."""
    t0 = ev["ts"]
    closes = [(b[0] + timedelta(minutes=1), b[4]) for b in bars]
    base = None; series = []
    for t, c in closes:
        if t >= t0:
            if base is None:
                base = c
            series.append((t, c))
    if base is None:
        return None
    sign = 1 if ev["direction"] == "bull" else -1
    out = {}
    for mins, key in ((5, "fwd5"), (15, "fwd15"), (30, "fwd30")):
        tgt = t0 + timedelta(minutes=mins)
        val = None
        for t, c in series:
            if t >= tgt:
                val = c; break
        out[key] = round(sign * (val - base), 2) if val is not None else None
    win = [c for t, c in series if t <= t0 + timedelta(minutes=30)]
    if win:
        out["mfe30"] = round(sign * (max(win) - base) if sign > 0 else sign * (min(win) - base), 2)
        out["mae30"] = round(sign * (min(win) - base) if sign > 0 else sign * (max(win) - base), 2)
    else:
        out["mfe30"] = out["mae30"] = None
    return out

# ---------------- cross-symbol modules (VIX, rates) ----------------

EXTREME_TYPES = {"rsi_extreme", "vwap_stretch", "vix_spike", "vix_rollover",
                 "vix_divergence", "vix_term_stress", "yield_spike", "yield_rollover",
                 "vol_ignition"}

def _close_map(bars):
    return {b[0]: b[4] for b in bars}

def _at_or_before(ts_sorted, cmap, t):
    val = None
    for ts in ts_sorted:
        if ts > t:
            break
        val = cmap[ts]
    return val

def detect_vix_events(spy_bars, vix_bars, vix9d_bars):
    """VIX extreme/divergence events. Scored against SPY (the tradable);
    `spot` recorded is the SPY price, VIX values live in detail."""
    if not spy_bars or not vix_bars:
        return []
    events = []
    vmap = _close_map(vix_bars); vts = sorted(vmap)
    nmap = _close_map(vix9d_bars) if vix9d_bars else {}
    smap = _close_map(spy_bars)
    vix_open = vix_bars[0][4]
    vix_high = -1.0; vix_high_ts = None; spike_armed = True
    rollover_armed = True; term_armed = True; last_div_ts = None
    spy_low = float("inf")
    for b in spy_bars:
        t_close = b[0] + timedelta(minutes=1)
        v = _at_or_before(vts, vmap, b[0])
        if v is None:
            continue
        if v > vix_high:
            vix_high = v; vix_high_ts = b[0]
            rollover_armed = True
        if v < vix_high * 0.95:
            spike_armed = True
        spy_low = min(spy_low, b[3])
        et = b[0].astimezone(ET)
        spot = b[4]
        # vix_spike: new session high >= open+10%, after 10:00 ET
        if (v >= vix_high - 1e-9 and v >= vix_open * 1.10 and spike_armed
                and (et.hour, et.minute) >= (10, 0)):
            events.append(dict(ts=t_close, type="vix_spike", direction="bull",
                               spot=spot, symbol="VIX", score_symbol="SPY",
                               detail={"vix": round(v, 2), "vix_open": round(vix_open, 2)}))
            spike_armed = False
        # vix_rollover: VIX >=7% off its high (high >=30m old), SPY near lows
        if (rollover_armed and vix_high_ts is not None
                and (b[0] - vix_high_ts).total_seconds() >= 1800
                and v <= vix_high * 0.93 and spot <= spy_low * 1.0035):
            events.append(dict(ts=t_close, type="vix_rollover", direction="bull",
                               spot=spot, symbol="VIX", score_symbol="SPY",
                               detail={"vix": round(v, 2), "vix_high": round(vix_high, 2),
                                       "spy_at_low": round(spy_low, 2)}))
            rollover_armed = False
        # vix term stress: VIX - VIX9D >= +2.0 (front-end fear extreme)
        if nmap:
            n = _at_or_before(sorted(nmap), nmap, b[0])
            if n is not None:
                spread = v - n
                if spread >= 2.0 and term_armed:
                    events.append(dict(ts=t_close, type="vix_term_stress", direction="bull",
                                       spot=spot, symbol="VIX", score_symbol="SPY",
                                       detail={"vix": round(v, 2), "vix9d": round(n, 2),
                                               "spread": round(spread, 2)}))
                    term_armed = False
                if spread < 1.0:
                    term_armed = True
    # vix_divergence: SPY 5-min bar prints a NEW session low after 10:30 ET
    # while VIX sits >=3% below its session high (fear not confirming)
    b5 = agg5(spy_bars)
    run_low = float("inf"); vix_high = -1.0
    for i, b in enumerate(b5):
        v = _at_or_before(vts, vmap, b[0])
        if v is not None:
            vix_high = max(vix_high, v)
        is_new_low = b[3] < run_low
        run_low = min(run_low, b[3])
        et = b[0].astimezone(ET)
        if (is_new_low and i > 0 and (et.hour, et.minute) >= (10, 30)
                and v is not None and vix_high > 0 and v <= vix_high * 0.97):
            ts = b[0] + timedelta(minutes=5)
            if last_div_ts is None or (ts - last_div_ts).total_seconds() >= 900:
                events.append(dict(ts=ts, type="vix_divergence", direction="bull",
                                   spot=b[4], symbol="VIX", score_symbol="SPY",
                                   detail={"vix": round(v, 2), "vix_high": round(vix_high, 2),
                                           "spy_low": round(b[3], 2)}))
                last_div_ts = ts
    return events

def detect_rates_events(spy_bars, tnx_bars):
    """10Y yield (^TNX, %) spike/rollover events, scored against SPY."""
    if not spy_bars or not tnx_bars:
        return []
    events = []
    tmap = _close_map(tnx_bars); tts = sorted(tmap)
    day_open = tnx_bars[0][4]
    y_high = -1.0; y_high_ts = None; spike_armed = True; roll_armed = True
    spy_low = float("inf")
    for b in spy_bars:
        t_close = b[0] + timedelta(minutes=1)
        y = _at_or_before(tts, tmap, b[0])
        if y is None:
            continue
        if y > y_high:
            y_high = y; y_high_ts = b[0]; roll_armed = True
        if y < y_high - 0.03:
            spike_armed = True
        spy_low = min(spy_low, b[3])
        et = b[0].astimezone(ET)
        if (y >= y_high - 1e-9 and y >= day_open + 0.08 and spike_armed
                and (et.hour, et.minute) >= (9, 30)):
            events.append(dict(ts=t_close, type="yield_spike", direction="bear",
                               spot=b[4], symbol="TNX", score_symbol="SPY",
                               detail={"tnx": round(y, 3), "tnx_open": round(day_open, 3)}))
            spike_armed = False
        if (roll_armed and y_high_ts is not None
                and (b[0] - y_high_ts).total_seconds() >= 2700
                and y <= y_high - 0.05 and b[4] <= spy_low * 1.005):
            events.append(dict(ts=t_close, type="yield_rollover", direction="bull",
                               spot=b[4], symbol="TNX", score_symbol="SPY",
                               detail={"tnx": round(y, 3), "tnx_high": round(y_high, 3),
                                       "spy_at_low": round(spy_low, 2)}))
            roll_armed = False
    return events

# ---------------- storage ----------------

def db_connect():
    con = sqlite3.connect(DB_PATH)
    cols = [r[1] for r in con.execute("PRAGMA table_info(indicator_events)").fetchall()]
    if cols and "symbol" not in cols:
        # migrate: add symbol (default SPY) + widen the uniqueness key
        con.execute("""CREATE TABLE indicator_events_v2 (
            id INTEGER PRIMARY KEY,
            day TEXT NOT NULL, ts_utc TEXT NOT NULL, ts_et TEXT NOT NULL,
            symbol TEXT NOT NULL DEFAULT 'SPY',
            type TEXT NOT NULL, direction TEXT NOT NULL, spot REAL,
            detail TEXT, fwd5 REAL, fwd15 REAL, fwd30 REAL,
            mfe30 REAL, mae30 REAL, scored INTEGER DEFAULT 0,
            UNIQUE (ts_utc, type, direction, symbol))""")
        con.execute("""INSERT INTO indicator_events_v2
            (id, day, ts_utc, ts_et, symbol, type, direction, spot, detail,
             fwd5, fwd15, fwd30, mfe30, mae30, scored)
            SELECT id, day, ts_utc, ts_et, 'SPY', type, direction, spot, detail,
             fwd5, fwd15, fwd30, mfe30, mae30, scored FROM indicator_events""")
        con.execute("DROP TABLE indicator_events")
        con.execute("ALTER TABLE indicator_events_v2 RENAME TO indicator_events")
        con.commit()
    con.execute("""CREATE TABLE IF NOT EXISTS indicator_events (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL, ts_utc TEXT NOT NULL, ts_et TEXT NOT NULL,
        symbol TEXT NOT NULL DEFAULT 'SPY',
        type TEXT NOT NULL, direction TEXT NOT NULL, spot REAL,
        detail TEXT, fwd5 REAL, fwd15 REAL, fwd30 REAL,
        mfe30 REAL, mae30 REAL, scored INTEGER DEFAULT 0,
        UNIQUE (ts_utc, type, direction, symbol))""")
    return con

def store_events(con, day, events, bars_by_symbol):
    new = []
    for e in events:
        ts_utc = e["ts"].astimezone(timezone.utc).isoformat()
        ts_et = e["ts"].astimezone(ET).strftime("%Y-%m-%d %H:%M")
        sbars = bars_by_symbol.get(e.get("score_symbol", "SPY"), [])
        sc = score_event(e, sbars) or {}
        scored = 1 if sc.get("fwd30") is not None else 0
        try:
            con.execute(
                "INSERT INTO indicator_events (day, ts_utc, ts_et, symbol, type, direction, spot, detail, fwd5, fwd15, fwd30, mfe30, mae30, scored) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (day, ts_utc, ts_et, e.get("symbol", "SPY"), e["type"], e["direction"], round(e["spot"], 2),
                 json.dumps(e["detail"]), sc.get("fwd5"), sc.get("fwd15"), sc.get("fwd30"),
                 sc.get("mfe30"), sc.get("mae30"), scored))
            new.append(e)
            with open(JSONL_PATH, "a") as f:
                f.write(json.dumps({"ts_et": ts_et, "symbol": e.get("symbol", "SPY"),
                                    "type": e["type"], "direction": e["direction"],
                                    "spot": round(e["spot"], 2), "detail": e["detail"],
                                    "fwd5": sc.get("fwd5"), "fwd15": sc.get("fwd15"),
                                    "fwd30": sc.get("fwd30"), "mfe30": sc.get("mfe30"),
                                    "mae30": sc.get("mae30")}) + "\n")
        except sqlite3.IntegrityError:
            pass
    con.commit()
    return new

def fmt_event(e):
    et = e["ts"].astimezone(ET).strftime("%H:%M")
    return f"{e.get('symbol', 'SPY')} {e['type']} {e['direction']} | {et} ET | spot {e['spot']:.2f} | {json.dumps(e['detail'])}"

# ---------------- main ----------------

def collect(day):
    """Fetch all symbols for a session and detect every module's events.
    Returns (events, bars_by_symbol). `day` None = today."""
    spy = fetch_bars(day, "SPY")
    if not spy:
        return [], {}
    qqq = fetch_bars(day, "QQQ")
    vix = fetch_bars(day, "%5EVIX", equity=False)
    vix9d = fetch_bars(day, "%5EVIX9D", equity=False)
    tnx = fetch_bars(day, "%5ETNX", start_hm=(8, 30), equity=False)
    bars_map = {"SPY": spy, "QQQ": qqq, "VIX": vix, "TNX": tnx}
    events = detect_events(spy, "SPY", True)
    if qqq:
        events += detect_events(qqq, "QQQ", True)
    events += detect_vix_events(spy, vix, vix9d)
    events += detect_rates_events(spy, tnx)
    events.sort(key=lambda e: e["ts"])
    return events, bars_map

def enrich_prints(con, day, events):
    """Context tags for vol_ignition events (Anik 2026-10-14, from the
    5-day print backtest): cluster = another print within the prior 30 min
    on the same symbol (Oct 8 pattern: prints clustering mid-collapse did
    NOT mark the low); prints_60m = count in the trailing hour;
    budget_left = SPY expected-move budget remaining at print time, from
    tape.db snapshots (Oct 14 pattern: the working capitulation print came
    isolated, with the budget mostly spent)."""
    prints = [e for e in events if e["type"] == "vol_ignition"]
    if not prints:
        return
    by_sym = {}
    for e in prints:
        by_sym.setdefault(e.get("symbol", "SPY"), []).append(e)
    for sym, evs in by_sym.items():
        evs.sort(key=lambda e: e["ts"])
        for i, e in enumerate(evs):
            prior = [p for p in evs[:i] if (e["ts"] - p["ts"]).total_seconds() <= 3600]
            e["detail"]["prints_60m"] = len(prior) + 1
            e["detail"]["cluster"] = any((e["ts"] - p["ts"]).total_seconds() <= 1800 for p in prior)
    # SPY move-budget series for the day (first snapshot = denominator)
    rows = con.execute("""SELECT ts, exp_move_dollars, exp_move_rem_dollars
                          FROM snapshots WHERE market_open=1 ORDER BY ts""").fetchall()
    series = []
    full = None
    for ts_s, em, rem in rows:
        ts = datetime.fromisoformat(ts_s)
        if ts.astimezone(ET).date().isoformat() != day:
            continue
        if full is None and em:
            full = em
        if full and rem:
            series.append((ts, rem / full))
    for e in prints:
        val = None
        for ts, bl in series:
            if ts <= e["ts"]:
                val = bl
            else:
                break
        e["detail"]["budget_left"] = round(val, 2) if val is not None else None

def reversals_report(con, day):
    """Major SPY turns (>= $2 follow-through within 30m of a 5-min swing)
    and every stored event in the 20 minutes before each turn."""
    spy = fetch_bars(day, "SPY")
    if not spy:
        print("NO_BARS")
        return
    b5 = agg5(spy)
    turns = []
    for i in range(1, len(b5) - 1):
        nxt = b5[i + 1:i + 7]
        if not nxt:
            continue
        if b5[i][3] < b5[i - 1][3] and b5[i][3] <= b5[i + 1][3]:
            if max(x[4] for x in nxt) - b5[i][3] >= 2.00:
                turns.append((b5[i][0] + timedelta(minutes=5), "LOW", b5[i][3]))
        if b5[i][2] > b5[i - 1][2] and b5[i][2] >= b5[i + 1][2]:
            if b5[i][2] - min(x[4] for x in nxt) >= 2.00:
                turns.append((b5[i][0] + timedelta(minutes=5), "HIGH", b5[i][2]))
    print(f"{day}: {len(turns)} major turns")
    for ts, kind, px in turns:
        lo = (ts - timedelta(minutes=20)).astimezone(timezone.utc).isoformat()
        hi = (ts + timedelta(minutes=5)).astimezone(timezone.utc).isoformat()
        rows = con.execute("""SELECT ts_et, symbol, type, direction FROM indicator_events
            WHERE ts_utc BETWEEN ? AND ? ORDER BY ts_utc""", (lo, hi)).fetchall()
        print(f"\nTURN {kind} {ts.astimezone(ET).strftime('%H:%M')} ET @ {px:.2f} — {len(rows)} events in prior 20m:")
        for r in rows:
            print(f"  {r[0][11:]} {r[1]} {r[2]} {r[3]}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", metavar="YYYY-MM-DD")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--reversals", metavar="YYYY-MM-DD")
    args = ap.parse_args()
    con = db_connect()

    if args.report:
        rows = con.execute("""SELECT symbol, type, direction, COUNT(*), SUM(scored),
            ROUND(AVG(CASE WHEN fwd30>0 THEN 1.0 ELSE 0 END)*100,0),
            ROUND(AVG(fwd30),2), ROUND(AVG(mfe30),2), ROUND(AVG(mae30),2)
            FROM indicator_events GROUP BY symbol, type, direction ORDER BY symbol, type, direction""").fetchall()
        print(f"{'sym':5} {'type':16} {'dir':5} {'n':>4} {'scored':>6} {'fwd30win%':>9} {'avg30':>7} {'avgMFE':>7} {'avgMAE':>7}")
        for r in rows:
            print(f"{r[0]:5} {r[1]:16} {r[2]:5} {r[3]:>4} {r[4] or 0:>6} {r[5] if r[5] is not None else '-':>9} {r[6] if r[6] is not None else '-':>7} {r[7] if r[7] is not None else '-':>7} {r[8] if r[8] is not None else '-':>7}")
        return

    if args.reversals:
        reversals_report(con, args.reversals)
        return

    day = args.backfill or datetime.now(ET).date().isoformat()
    events, bars_map = collect(args.backfill)
    if not events and not bars_map:
        print("NO_BARS")
        return
    enrich_prints(con, day, events)
    new = store_events(con, day, events, bars_map)
    if args.backfill:
        print(f"backfill {day}: {len(events)} events ({len(new)} newly stored)")
        for e in events:
            sc = score_event(e, bars_map.get(e.get("score_symbol", "SPY"), [])) or {}
            print(" ", fmt_event(e), "| fwd30:", sc.get("fwd30"), "mfe:", sc.get("mfe30"), "mae:", sc.get("mae30"))
    else:
        for e in new:
            if e["type"] == "STACK":
                prefix = "STACK "
            elif e["type"] in EXTREME_TYPES:
                prefix = "EXTREME "
            else:
                prefix = "EVENT "
            print(prefix + fmt_event(e))
        if not new:
            print("QUIET")

if __name__ == "__main__":
    main()
