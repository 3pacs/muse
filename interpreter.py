#!/usr/bin/env python3
"""
0DTE options interpreter for stepdad.finance.

Polls the live inputs at gex.stepdad.finance (thinkorswim RTD collector):
  - /api/state     -> live SPY quote + 1-min bars
  - /api/contracts -> full 0DTE chain with bid/ask, volume, OI, Greeks

...and emits four derived interpretation feeds:
  - /feed/gamma       net GEX by strike, gamma flip, call/put walls
  - /feed/flow        put/call ratios, elevated volume activity, top volume activity
  - /feed/vanna-charm dealer vanna/charm exposure (BS-derived)
  - /feed/iv          skew, 25-delta risk reversal, smile shape
  - /feed/all         everything in one payload
  - /stream           SSE push of the latest snapshot

Stdlib only. Run:  python3 interpreter.py [--port 8787] [--poll 30]
"""

import argparse
import json
import math
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- config

STATE_URL = "http://gex.stepdad.finance/api/state"
CONTRACTS_URL = "http://gex.stepdad.finance/api/contracts"

RISK_FREE = 0.043      # ~ current T-bill; documented assumption
DIV_YIELD = 0.013      # SPY trailing div yield; documented assumption
CONTRACT_MULT = 100.0
PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")
YEAR_SECONDS = 365.25 * 24 * 3600

SNAPSHOT = {"status": "starting", "updated_at": None}
LOCK = threading.Lock()

# ---------------------------------------------------------------- math

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def bs_d1_d2(S, K, T, r, q, sigma):
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return None, None
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)

def vanna(S, K, T, r, q, sigma):
    """dDelta/dVol (per 1.0 vol)."""
    d1, d2 = bs_d1_d2(S, K, T, r, q, sigma)
    if d1 is None:
        return 0.0
    return -math.exp(-q * T) * norm_pdf(d1) * d2 / sigma

def bs_gamma(S, K, T, r, q, sigma):
    d1, _ = bs_d1_d2(S, K, T, r, q, sigma)
    if d1 is None:
        return 0.0
    return math.exp(-q * T) * norm_pdf(d1) / (S * sigma * math.sqrt(T))

def bs_delta(S, K, T, r, q, sigma, is_call=True):
    d1, _ = bs_d1_d2(S, K, T, r, q, sigma)
    if d1 is None:
        return 0.0
    return math.exp(-q * T) * (norm_cdf(d1) if is_call else norm_cdf(d1) - 1.0)

def _num(x, default=0.0):
    if x in (None, "--", ""):
        return default
    try:
        return float(str(x).replace(",", ""))
    except (ValueError, TypeError):
        return default

def charm(S, K, T, r, q, sigma, is_call=True):
    """Trader's charm: delta decay per 1.0 year of clock time (=-dDelta/dT,
    T in years). Positive = delta rises as clock time passes (e.g. ITM
    long call pinning toward 1). Hedge with the opposite sign."""
    d1, d2 = bs_d1_d2(S, K, T, r, q, sigma)
    if d1 is None:
        return 0.0
    e_qrt = math.exp(-q * T)
    n1 = norm_pdf(d1)
    term = n1 * (2.0 * (r - q) * T - d2 * sigma * math.sqrt(T)) / (2.0 * T * sigma * math.sqrt(T))
    term += -q * (norm_cdf(d1) if is_call else (norm_cdf(d1) - 1.0))
    return -e_qrt * term

# ---------------------------------------------------------------- fetch

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "stepdad-0dte-interpreter/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

_NQ = {"at": 0.0, "as_of": None, "label": None, "rows": [], "stale": False}
NQ_TTL = 300        # refresh wings every 5 min
NQ_MAX_STALE = 1800  # on failure, serve same-label cache at most 30 min


def _nasdaq_label(now):
    et = now.astimezone(ET)
    return et.strftime("%b ") + str(et.day)  # e.g. "Sep 28"


def fetch_nasdaq_0dte(now):
    """Wide 0DTE chain from Nasdaq public API (~15min delayed).
    Cached 5 min; on refresh failure the previous rows are served for at
    most 30 min and only when they belong to today's expiry label. Older
    or foreign-label cache is discarded -> wings reported unavailable
    (never relabelled across dates)."""
    label = _nasdaq_label(now)
    age = time.time() - _NQ["at"]
    if _NQ["rows"] and _NQ["label"] == label and age < NQ_TTL:
        _NQ["stale"] = False
        return _NQ["rows"]
    try:
        url = "https://api.nasdaq.com/api/quote/SPY/option-chain?assetclass=etf"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))["data"]
        out = []
        for row in data["table"]["rows"]:
            if row.get("expiryDate") != label or not row.get("strike"):
                continue
            k = _num(row["strike"])
            out.append({
                "strike": k,
                "call": {"bid": _num(row["c_Bid"], None), "ask": _num(row["c_Ask"], None),
                         "volume": _num(row["c_Volume"]), "oi": _num(row["c_Openinterest"])},
                "put": {"bid": _num(row["p_Bid"], None), "ask": _num(row["p_Ask"], None),
                        "volume": _num(row["p_Volume"]), "oi": _num(row["p_Openinterest"])},
            })
        if out:
            _NQ.update(at=time.time(),
                       as_of=datetime.now(timezone.utc).isoformat(),
                       label=label, rows=out, stale=False)
            return out
    except Exception:
        pass
    # refresh failed (or returned no rows for this label): serve stale
    # only within policy; otherwise wings are unavailable
    if _NQ["rows"] and _NQ["label"] == label and age < NQ_MAX_STALE:
        _NQ["stale"] = True
        return _NQ["rows"]
    _NQ.update(rows=[], stale=False, as_of=None, label=None)
    return []


def nasdaq_provenance():
    """Source metadata for the Nasdaq wing cache (F01/F03)."""
    return {"as_of": _NQ["as_of"], "label": _NQ["label"],
            "delay": "~15min", "stale": _NQ["stale"],
            "n_rows": len(_NQ["rows"])}

def market_open_now(now_utc):
    pt = now_utc.astimezone(PT)
    if pt.weekday() >= 5:
        return False
    mins = pt.hour * 60 + pt.minute
    return 6 * 60 + 30 <= mins < 13 * 60

def seconds_to_expiry(now_utc, expiry_date):
    """Seconds from now until 16:00 ET on expiry date (0DTE => today)."""
    exp_close = datetime(expiry_date.year, expiry_date.month, expiry_date.day,
                         16, 0, 0, tzinfo=ET)
    return max((exp_close - now_utc).total_seconds(), 60.0)

# ---------------------------------------------------------------- positioning analytics
# Blended from the open-source GEX dashboards (GammaGrid, EzOptions-Schwab,
# traders-edge-mcp, helenus, flashalpha): expected move, dealer hedge buckets,
# pin score. Regime/pinning only — no directional signal is computed here.

def _mid(s):
    if not s:
        return None
    b, a = s.get("bid"), s.get("ask")
    if b is None or a is None:
        return None
    try:
        m = (float(b) + float(a)) / 2.0
        return m if m > 0 else None
    except (ValueError, TypeError):
        return None

def compute_positioning(by_strike, strikes, S, sec_to_exp, flip=None, regime=None):
    """Expected move, dealer hedge buckets, pin score, reversal conditions.

    All regime/pinning reads. Nothing here predicts direction: gamma evidence
    supports vol regime (damp vs trend) and pinning pull, not reversals.
    The reversal_watch block states mean-reversion CONDITIONS; the milestone
    jobs score whether they preceded actual reversals."""
    pos = {}
    if not strikes or S <= 0:
        return pos

    # ---- expected move from ATM straddle ----
    atm_k = min(strikes, key=lambda k: abs(k - S))
    d = by_strike.get(atm_k, {})
    mc, mp_ = _mid(d.get("call")), _mid(d.get("put"))
    if mc is not None and mp_ is not None:
        straddle = mc + mp_
        # R8: a current-maturity quote already prices the REMAINING horizon.
        # The old sqrt(time-left/6.5h) rescale double-counted time decay and
        # mislabeled a mid-session quote as a full-session move. remaining_*
        # are the quoted values, identical by construction.
        pos["expected_move"] = {
            "dollars": round(straddle, 2),
            "dollars_kind": "quoted",  # ATM straddle mid: the market's own price
            "pct": round(100.0 * straddle / S, 3),
            "remaining_dollars": round(straddle, 2),
            "remaining_kind": "quoted",
            "remaining_pct": round(100.0 * straddle / S, 3),
            "atm_strike": atm_k,
            "note": ("dollars = quoted ATM straddle mid = market-implied expected "
                     "move to expiry; no sqrt(time) rescaling — the current-maturity "
                     "quote already reflects the remaining horizon (R8)"),
        }

    # ---- dealer hedge buckets: shares dealers would need to trade (scenario) ----
    # dealer gamma (shares per $1 move) = +(cust call gamma - cust put gamma) * 100
    # standard GEX convention: dealers long calls / short puts
    dg_by_strike = {}
    for k in strikes:
        dd = by_strike[k]
        cg = (dd.get("call", {}).get("gamma") or 0.0) * (dd.get("call", {}).get("oi") or 0.0)
        pg = (dd.get("put", {}).get("gamma") or 0.0) * (dd.get("put", {}).get("oi") or 0.0)
        dg_by_strike[k] = (cg - pg) * CONTRACT_MULT
    total_dg = sum(dg_by_strike.values())
    buckets = []
    for bp in (10, 25, 50, 100):
        dS = S * bp / 10000.0
        hedge_shares = -total_dg * dS  # trade opposite the delta change
        buckets.append({
            "shock_bp": bp,
            "dS": round(dS, 2),
            "notional_m": round(hedge_shares * S / 1e6, 1),
            "direction": "buy" if hedge_shares > 0 else "sell",
        })
    pos["hedge_buckets"] = buckets
    # F08: inventory scenarios, not observed executions
    pos["hedge_buckets_note"] = (
        "inventory scenarios: signed $m dealers would need to trade to re-hedge "
        "each spot shock under standard dealer positioning (long calls/short puts); "
        "model output, not observed executions")
    pos["dealer_gamma_notional_m_per_pt"] = round(total_dg * S / 1e6, 1)

    # ---- pin score 0-100: concentration + proximity to magnet + time elapsed ----
    rows = []
    for k in strikes:
        dd = by_strike[k]
        cg = (dd.get("call", {}).get("gamma") or 0.0) * (dd.get("call", {}).get("oi") or 0.0)
        pg = (dd.get("put", {}).get("gamma") or 0.0) * (dd.get("put", {}).get("oi") or 0.0)
        rows.append((k, (cg - pg) * S * S * CONTRACT_MULT * 0.01 / 1e6))
    abs_sum = sum(abs(v) for _, v in rows)
    if abs_sum > 0:
        sh = [abs(v) / abs_sum for _, v in rows]
        n = len(sh)
        hhi = sum(s * s for s in sh)
        hhi_norm = (hhi - 1.0 / n) / (1.0 - 1.0 / n) if n > 1 else 1.0
        magnet = max(rows, key=lambda t: abs(t[1]))[0]
        prox = math.exp(-abs(S - magnet) / (0.005 * S))
        elapsed = max(0.0, min(1.0, 1.0 - sec_to_exp / 23400.0))
        pos["pin_score"] = round(100.0 * (0.40 * hhi_norm + 0.35 * prox + 0.25 * elapsed), 1)
        pos["pin_magnet"] = magnet
        pos["pin_components"] = {
            "concentration": round(hhi_norm, 3),
            "proximity": round(prox, 3),
            "time_elapsed": round(elapsed, 3),
        }
    pos["assumptions"] = ("dealers long calls / short puts (standard GEX convention); "
                          "gamma x OI; sqrt time scaling; pinning only, no directional signal")

    # ---- reversal watch: mean-reversion CONDITIONS, not a directional forecast ----
    rev = {}
    emr = (pos.get("expected_move") or {}).get("remaining_dollars")
    magnet = pos.get("pin_magnet")
    if magnet is not None and emr is not None and S > 0:
        disp = S - magnet
        stretched = abs(disp) > emr
        conds = []
        total_gex = sum(v for _, v in rows)
        if total_gex > 0 and stretched:
            conds.append(
                f"stretched ${abs(disp):.2f} from magnet vs ${emr:.2f} expected "
                f"move left, positive gamma -> snap-back conditions toward {magnet:.0f}")
        if (pos.get("pin_score") or 0) >= 70:
            conds.append(
                f"pin score {pos['pin_score']:.0f}: magnet {magnet:.0f} pulling into the close")
        if flip is not None and abs(S - flip) / S < 0.003:
            conds.append("sitting on the gamma flip — regime can change fast here")
        if total_gex < 0:
            conds.append("negative gamma: moves tend to extend, not reverse — don't fade the move")
        rev = {
            "magnet": magnet,
            "displacement_dollars": round(disp, 2),
            "displacement_pct": round(100.0 * disp / S, 3),
            "expected_move_remaining": round(emr, 2),
            "stretched": stretched,
            "flip_distance_dollars": round(S - flip, 2) if flip is not None else None,
            "conditions": conds,
            "note": "mean-reversion setup read, not a directional forecast",
        }
    pos["reversal_watch"] = rev
    return pos

# ---------------------------------------------------------------- interpret

def build_snapshot():
    now = datetime.now(timezone.utc)
    state = fetch_json(STATE_URL)
    contracts = fetch_json(CONTRACTS_URL)

    quote = state.get("quote", {}) or {}
    spot = float(quote.get("price") or 0)
    quote_as_of = quote.get("as_of")

    # R7: reject clocks from the future. A quote newer than now+5min is
    # quarantined, never served as a live read.
    if quote_as_of:
        try:
            _qts = datetime.fromisoformat(quote_as_of)
            if _qts.tzinfo is None:
                _qts = _qts.replace(tzinfo=timezone.utc)
            if (_qts - now).total_seconds() > 300:
                return {"status": "quarantined",
                        "quarantine_reason":
                            f"quote_as_of {quote_as_of} is in the future",
                        "updated_at": now.isoformat(),
                        "market_open": False,
                        "quote_as_of": quote_as_of}
        except (ValueError, TypeError):
            pass  # unparseable quote time: leave to staleness handling below

    clist = contracts.get("contracts") or []
    # R7: the chain's provider and timestamp come from the CHAIN payload.
    # Never upgrade a chain to realtime from the quote's provider (F01/R7).
    chain_provider = contracts.get("provider") or "rtd"
    row_times = {c.get("as_of") for c in clist if c.get("as_of")}
    chain_as_of = contracts.get("as_of") or (row_times.pop() if len(row_times) == 1 else None)
    chain_time_note = None
    if chain_provider == "rtd":
        # the genuine RTD poll: quote and chain share the poll clock
        chain_delay = "realtime"
        chain_as_of = chain_as_of or quote_as_of
    else:
        chain_delay = contracts.get("delay") or "unknown"
        if chain_as_of:
            try:
                _cts = datetime.fromisoformat(chain_as_of)
                if _cts.tzinfo is None:
                    _cts = _cts.replace(tzinfo=timezone.utc)
                if (_cts - now).total_seconds() > 300:
                    chain_time_note = f"chain as_of {chain_as_of} is in the future; treated as unknown"
                    chain_as_of = None
            except (ValueError, TypeError):
                chain_time_note = f"chain as_of {chain_as_of} unparseable; treated as unknown"
                chain_as_of = None
        # unknown source age remains unknown: never inherit the quote's time
    today_et = str(now.astimezone(ET).date())
    # 0DTE = today's expiry only; the feed also carries later weeklies
    clist = [c for c in clist if c.get("expiry") == today_et]
    if not clist:
        raise ValueError("no 0DTE contracts in feed")
    expiry = today_et
    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    T = seconds_to_expiry(now, exp_date) / YEAR_SECONDS

    by_strike = {}
    for c in clist:
        k = float(c["strike"])
        d = by_strike.setdefault(k, {"strike": k})
        side = "call" if c.get("side") == "C" else "put"
        prev = d.get(side)
        rec = {
            "bid": c.get("bid"), "ask": c.get("ask"),
            "bid_size": c.get("bid_size"), "ask_size": c.get("ask_size"),
            "volume": float(c.get("volume") or 0),
            "oi": float(c.get("open_interest") or 0),
            "delta": c.get("delta"), "gamma": float(c.get("gamma") or 0),
            "theta": c.get("theta"), "iv": c.get("iv"),
            "greeks": "observed",  # from the upstream RTD payload (F07)
        }
        if prev:  # aggregate duplicate roots: sum flow, keep busiest quote
            rec["volume"] += prev["volume"]
            rec["oi"] += prev["oi"]
            if prev["volume"] > float(c.get("volume") or 0):
                for f in ("bid", "ask", "bid_size", "ask_size", "delta", "gamma", "theta", "iv"):
                    rec[f] = prev[f]
        d[side] = rec
        d["src"] = chain_provider  # R7: the chain's own declared provider

    # ---- widen: Nasdaq delayed chain fills the wings around live RTD center ----
    # ATM IV from RTD for BS gamma on wing strikes
    atm_k_rtd = min(by_strike, key=lambda k: abs(k - spot)) if by_strike else None
    atm_ivs = []
    if atm_k_rtd is not None:
        for side in ("call", "put"):
            iv = by_strike[atm_k_rtd].get(side, {}).get("iv")
            if iv:
                atm_ivs.append(iv)
    atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else 0.18
    n_nasdaq = 0
    try:
        for q in fetch_nasdaq_0dte(now):
            k = q["strike"]
            if k in by_strike:
                continue
            d = {"strike": k, "src": "nasdaq_delayed"}
            for side in ("call", "put"):
                s = q[side]
                is_call = side == "call"
                gam = bs_gamma(spot, k, T, RISK_FREE, DIV_YIELD, atm_iv)
                d[side] = {
                    "bid": s["bid"], "ask": s["ask"],
                    "bid_size": None, "ask_size": None,
                    "volume": s["volume"], "oi": s["oi"],
                    "delta": round(bs_delta(spot, k, T, RISK_FREE, DIV_YIELD, atm_iv, is_call), 4),
                    "gamma": round(gam, 4), "theta": None, "iv": None,
                    "greeks": "modeled_atm_iv",  # BS at ATM IV; not vendor quotes (F07)
                }
            by_strike[k] = d
            n_nasdaq += 1
    except Exception:
        pass  # wings optional; live center still served

    strikes = sorted(by_strike)
    S = spot
    nq_prov = nasdaq_provenance()
    chain_strikes = sum(1 for k in strikes if by_strike[k].get("src") == chain_provider)
    chain_src = {
        "as_of": chain_as_of, "delay": chain_delay,
        "n_strikes": chain_strikes,
    }
    if chain_time_note:
        chain_src["time_note"] = chain_time_note
    sources = {
        # R7: keyed by the chain's own provider; a delayed chain is never
        # presented as realtime, and its age is its own, not the quote's.
        chain_provider: chain_src,
        "nasdaq": {"as_of": nq_prov["as_of"], "delay": nq_prov["delay"],
                   "n_strikes": n_nasdaq, "stale": nq_prov["stale"]},
    }

    # ---- gamma map ----
    rows = []
    for k in strikes:
        d = by_strike[k]
        cg = d.get("call", {}).get("gamma", 0.0) * d.get("call", {}).get("oi", 0.0)
        pg = d.get("put", {}).get("gamma", 0.0) * d.get("put", {}).get("oi", 0.0)
        net_gex = (cg - pg) * S * S * CONTRACT_MULT * 0.01  # $m per 1% spot move
        # (v2 units; dealers long calls / short puts = std GEX convention)
        rows.append({"strike": k, "src": d.get("src", "unknown"),
                     "greeks": d.get("call", {}).get("greeks", "unknown"),
                     "net_gex_m": round(net_gex / 1e6, 2),
                     "call_gex_m": round(cg * S * S * CONTRACT_MULT * 0.01 / 1e6, 2),
                     "put_gex_m": round(-pg * S * S * CONTRACT_MULT * 0.01 / 1e6, 2)})
    total_gex_m = round(sum(r["net_gex_m"] for r in rows), 2)

    # ---- gamma flip: spot root(s) of net dealer gamma (F05/R1/R2) ----
    # Signed net dealer gamma over a hypothetical-spot domain, with IV frozen
    # PER CONTRACT LEG and OI frozen (scenario, not a prediction). The old
    # cumulative strike-GEX zero crossing is retired: it was not a spot level
    # where net gamma vanishes.
    #
    # Solver policy (declared):
    #   grid       N=2000 samples over [0.90*S, 1.10*S] (0.01% of spot / step)
    #   IV         frozen per leg; legs without a quoted IV use ATM IV
    #              (wings: modeled_atm_iv). Leg IVs are NEVER averaged across
    #              legs (R2: averaging erased real scenario roots).
    #   root       strict sign change between two consecutive samples, both
    #              with |v| > underflow_eps = max(1e-300, scale*1e-12), where
    #              scale = max |net gamma| on the grid (shares per $1).
    #              Exact floating-point zeros are NEVER promoted to roots:
    #              far-tail bs_gamma underflows to 0.0, a numeric artifact,
    #              not an inventory sign change (R1).
    #   tangency   a zero-touch without a sign change is not a root; the
    #              count of underflow/touchdown samples is reported, not rooted.
    #   refine     each bracket gets 80 bisection steps; the relative residual
    #              |g(root)|/scale is recorded as the conditioning diagnostic.
    #   dedupe     refined roots closer than 0.02 are merged (grid artifact).
    flip, flip_roots, flip_residuals = None, [], []
    flip_scale, flip_underflow_samples = 0.0, 0
    if S > 0 and T > 0:
        leg_ivs = {}
        for k in strikes:
            d = by_strike[k]
            for side in ("call", "put"):
                s = d.get(side)
                if s and (s.get("oi") or 0.0) > 0:
                    iv = s.get("iv") or atm_iv
                    leg_ivs[(k, side)] = iv if iv and iv > 0 else atm_iv

        def net_gamma_at(sp):
            tot = 0.0
            for k in strikes:
                d = by_strike[k]
                for side in ("call", "put"):
                    s = d.get(side)
                    if not s:
                        continue
                    oi = s.get("oi", 0.0) or 0.0
                    if oi <= 0:
                        continue
                    iv = leg_ivs.get((k, side)) or atm_iv
                    if iv <= 0:
                        continue
                    g = bs_gamma(sp, k, T, RISK_FREE, DIV_YIELD, iv)
                    tot += (oi * g if side == "call" else -oi * g) * CONTRACT_MULT
            return tot  # shares per $1; dealers long calls / short puts

        lo, hi, N = 0.90 * S, 1.10 * S, 2000
        vals = [net_gamma_at(lo + (hi - lo) * i / N) for i in range(N + 1)]
        flip_scale = max([abs(v) for v in vals] + [0.0])
        underflow_eps = max(1e-300, flip_scale * 1e-12)
        prev_sp, prev_v = lo, vals[0]
        for i in range(1, N + 1):
            sp, v = lo + (hi - lo) * i / N, vals[i]
            a_live = abs(prev_v) > underflow_eps
            b_live = abs(v) > underflow_eps
            if not b_live:
                flip_underflow_samples += 1
            if a_live and b_live and (prev_v < 0) != (v < 0):
                a, b, fa = prev_sp, sp, prev_v
                for _ in range(80):
                    c = 0.5 * (a + b)
                    fc = net_gamma_at(c)
                    if (fa < 0) == (fc < 0):
                        a, fa = c, fc
                    else:
                        b = c
                root = 0.5 * (a + b)
                resid = abs(net_gamma_at(root)) / flip_scale if flip_scale > 0 else 0.0
                flip_roots.append((round(root, 2), resid))
            prev_sp, prev_v = sp, v
        ded = []
        for r_, res_ in flip_roots:
            if not ded or abs(r_ - ded[-1][0]) > 0.02:
                ded.append((r_, res_))
        flip_roots = [r_ for r_, _ in ded]
        flip_residuals = [res_ for _, res_ in ded]
        if flip_roots:
            flip = min(flip_roots, key=lambda r_: abs(r_ - S))

    pos = [r for r in rows if r["net_gex_m"] > 0]
    neg = [r for r in rows if r["net_gex_m"] < 0]
    call_wall = max(pos, key=lambda r: r["net_gex_m"])["strike"] if pos else None
    put_wall = min(neg, key=lambda r: r["net_gex_m"])["strike"] if neg else None
    top_gamma = sorted(rows, key=lambda r: abs(r["net_gex_m"]), reverse=True)[:8]

    gamma = {
        "spot": S, "expiry": expiry,
        "gex_formula": "v2",
        "gex_units": "USD millions per 1% spot move",
        "net_gex_m": total_gex_m,
        "gamma_flip": flip,
        "gamma_flip_method": "spot_root_frozen_iv_oi",
        "gamma_flip_roots": flip_roots,
        # R1/R2 solver diagnostics: relative residuals per root, grid scale,
        # and the count of underflow/touchdown samples (never promoted).
        "gamma_flip_residuals": [round(r, 12) for r in flip_residuals],
        "gamma_flip_scale": flip_scale,
        "gamma_flip_underflow_samples": flip_underflow_samples,
        "gamma_flip_note": ("spot level(s) where net dealer gamma changes sign "
                            "(per-leg frozen IV/OI scenario); tangencies and "
                            "floating-point underflow zeros are never roots; "
                            "None = no sign change in ±10% domain"
                            if flip is None else None),
        "call_wall": call_wall, "put_wall": put_wall,
        "regime": ("positive-gamma (pinning)" if total_gex_m > 0 else
                   "negative-gamma (trending)" if total_gex_m < 0 else "neutral"),
        "by_strike": rows, "top_strikes": top_gamma,
    }

    # ---- max pain (classic: strike minimizing total option-holder payout) ----
    oi_strikes = [(k, by_strike[k].get("call", {}).get("oi", 0) or 0,
                   by_strike[k].get("put", {}).get("oi", 0) or 0) for k in strikes]
    oi_strikes = [(k, c, p) for k, c, p in oi_strikes if c > 0 or p > 0]

    def _pain(s):
        return sum(c * max(s - k, 0.0) + p * max(k - s, 0.0) for k, c, p in oi_strikes)

    max_pain = min(oi_strikes, key=lambda t: _pain(t[0]))[0] if oi_strikes else None
    gamma["max_pain"] = max_pain

    # ---- flow ----
    call_vol = sum(by_strike[k].get("call", {}).get("volume", 0) for k in strikes)
    put_vol = sum(by_strike[k].get("put", {}).get("volume", 0) for k in strikes)
    call_oi = sum(by_strike[k].get("call", {}).get("oi", 0) for k in strikes)
    put_oi = sum(by_strike[k].get("put", {}).get("oi", 0) for k in strikes)

    unusual = []
    for k in strikes:
        for side in ("call", "put"):
            s = by_strike[k].get(side)
            if not s or s["oi"] <= 0 or s["volume"] < 500:
                continue
            ratio = s["volume"] / s["oi"]
            if ratio >= 1.5:
                mid = ((s["bid"] or 0) + (s["ask"] or 0)) / 2
                unusual.append({"strike": k, "side": side,
                                "src": by_strike[k].get("src", "unknown"),
                                "unsigned": True,  # activity, not executions (F08)
                                "volume": s["volume"], "oi": s["oi"],
                                "vol_oi": round(ratio, 2),
                                "notional_k": round(mid * s["volume"] * CONTRACT_MULT / 1e3, 1)})
    unusual.sort(key=lambda x: x["vol_oi"], reverse=True)

    top_vol = sorted(
        ({"strike": k,
          "call_vol": by_strike[k].get("call", {}).get("volume", 0),
          "put_vol": by_strike[k].get("put", {}).get("volume", 0)} for k in strikes),
        key=lambda x: x["call_vol"] + x["put_vol"], reverse=True)[:8]

    flow = {
        "spot": S, "expiry": expiry,
        "pc_volume": round(put_vol / call_vol, 3) if call_vol else None,
        "pc_oi": round(put_oi / call_oi, 3) if call_oi else None,
        "call_volume": call_vol, "put_volume": put_vol,
        "call_oi": call_oi, "put_oi": put_oi,
        # F08: unsigned activity, never executions; no aggressor/open-close inferred
        "elevated_volume_activity": unusual[:12],
        "top_volume_activity": top_vol,
        "activity_note": ("unsigned volume activity (vol/OI>=1.5, >=500 contracts); "
                          "not executed flow; no aggressor side or open/close inferred"),
    }

    # ---- vanna / charm ----
    v_rows, total_vanna, total_charm = [], 0.0, 0.0
    for k in strikes:
        sv = sh = 0.0
        for side in ("call", "put"):
            s = by_strike[k].get(side)
            if not s:
                continue
            iv = s.get("iv") or atm_iv  # wings fall back to ATM IV
            if iv <= 0:
                continue
            is_call = side == "call"
            vn = vanna(S, k, T, RISK_FREE, DIV_YIELD, iv)
            ch = charm(S, k, T, RISK_FREE, DIV_YIELD, iv, is_call)
            shares = s["oi"] * CONTRACT_MULT
            # Hedge flow: opposes the position's delta change.
            # dealers long calls / short puts (std GEX convention).
            # vanna: delta change per +1 vol point = vn*0.01
            # charm: delta decay per clock hour = ch/(365.25*24)
            sign = 1.0 if is_call else -1.0
            sv += -sign * shares * vn * S * 0.01
            sh += -sign * shares * ch * S / (365.25 * 24.0)
        total_vanna += sv
        total_charm += sh
        if abs(sv) > 1 or abs(sh) > 1:
            v_rows.append({"strike": k, "vanna_k": round(sv / 1e3, 1), "charm_k": round(sh / 1e3, 1)})
    v_rows.sort(key=lambda r: abs(r["vanna_k"]), reverse=True)
    vanna_charm = {
        "spot": S, "expiry": expiry, "T_years": round(T, 6),
        "assumptions": {"r": RISK_FREE, "q": DIV_YIELD,
                        "dealer_position": "long calls / short puts",
                        "vanna_units": "$ delta-hedge flow per +1pt IV move (hedge opposes position change)",
                        "charm_units": "$ delta-hedge flow per 1hr clock decay (hedge opposes position change)"},
        "total_vanna_k": round(total_vanna / 1e3, 1),
        "total_charm_k": round(total_charm / 1e3, 1),
        "by_strike": v_rows[:12],
    }

    # ---- IV ----
    iv_rows = []
    for k in strikes:
        c, p = by_strike[k].get("call"), by_strike[k].get("put")
        if c and p and c.get("iv") and p.get("iv"):
            iv_rows.append({"strike": k, "call_iv": round(c["iv"], 4),
                            "put_iv": round(p["iv"], 4),
                            "put_minus_call": round(p["iv"] - c["iv"], 4)})
    atm_k = min(strikes, key=lambda k: abs(k - S)) if strikes else None
    atm_iv = next((r for r in iv_rows if r["strike"] == atm_k), None)

    def closest_delta(target, tol=0.05):
        # nearest strike delta to target; None when the best available is
        # farther than `tol` delta points away (F07: no far-away "25d" relabel)
        best = None
        for k in strikes:
            for side in ("call", "put"):
                s = by_strike[k].get(side)
                if s and s.get("delta") is not None and s.get("iv"):
                    if best is None or abs(s["delta"] - target) < abs(best[1] - target):
                        best = (s["iv"], s["delta"], k, side)
        if best is None or abs(best[1] - target) > tol:
            return None
        return best

    c25 = closest_delta(0.25)
    p25 = closest_delta(-0.25)
    rr25 = round(p25[0] - c25[0], 4) if c25 and p25 else None

    near = [r for r in iv_rows if abs(r["strike"] - S) / S <= 0.02]
    smile = None
    if near:
        ivs = [(r["call_iv"] + r["put_iv"]) / 2 for r in near]
        smile = {"width": round(max(ivs) - min(ivs), 4),
                 "min_iv_strike": near[ivs.index(min(ivs))]["strike"]}

    iv = {
        "spot": S, "expiry": expiry,
        "atm_strike": atm_k,
        "atm_call_iv": atm_iv["call_iv"] if atm_iv else None,
        "atm_put_iv": atm_iv["put_iv"] if atm_iv else None,
        "risk_reversal_25d": rr25,
        "risk_reversal_note": "put25 IV minus call25 IV; >0 = downside bid",
        "skew_by_strike": iv_rows,
        "smile_2pct": smile,
        "term_structure": None,
        "term_structure_note": "single-expiry (0DTE) feed; no term structure available",
    }

    # ---- positioning analytics: expected move, hedge buckets, pin score ----
    positioning = compute_positioning(by_strike, strikes, S, T * YEAR_SECONDS,
                                      flip=gamma.get("gamma_flip"),
                                      regime=gamma.get("regime"))

    return {
        "status": "ok",
        "updated_at": now.isoformat(),
        "market_open": market_open_now(now),
        "quote_as_of": quote_as_of,
        "spot": S, "expiry": expiry,
        "n_strikes": len(strikes),
        "n_strikes_rtd_live": sum(1 for k in strikes if by_strike[k].get("src") == "rtd"),
        "n_strikes_nasdaq_delayed": n_nasdaq,
        "sources": sources,
        "gamma": gamma, "flow": flow,
        "vanna_charm": vanna_charm, "iv": iv,
        "positioning": positioning,
    }

# ---------------------------------------------------------------- poll loop

def poll_forever(interval):
    global SNAPSHOT
    while True:
        try:
            snap = build_snapshot()
        except Exception as e:  # never kill the loop on a bad poll
            snap = {"status": "error", "error": str(e),
                    "updated_at": datetime.now(timezone.utc).isoformat()}
        with LOCK:
            SNAPSHOT = snap
        time.sleep(interval)

# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with LOCK:
            snap = dict(SNAPSHOT)
        meta = {k: snap.get(k) for k in ("status", "updated_at", "market_open", "spot",
                                         "expiry", "n_strikes", "n_strikes_rtd_live",
                                         "n_strikes_nasdaq_delayed")}
        if self.path == "/feed/all":
            self._send(snap)
        elif self.path == "/feed/gamma":
            self._send(meta | {"gamma": snap.get("gamma")})
        elif self.path == "/feed/flow":
            self._send(meta | {"flow": snap.get("flow")})
        elif self.path == "/feed/vanna-charm":
            self._send(meta | {"vanna_charm": snap.get("vanna_charm")})
        elif self.path == "/feed/iv":
            self._send(meta | {"iv": snap.get("iv")})
        elif self.path == "/feed/positioning":
            self._send(meta | {"positioning": snap.get("positioning")})
        elif self.path == "/feed/maxpain":
            g = snap.get("gamma") or {}
            self._send(meta | {"max_pain": g.get("max_pain"),
                               "call_wall": g.get("call_wall"),
                               "put_wall": g.get("put_wall")})
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    with LOCK:
                        s = dict(SNAPSHOT)
                    msg = f"data: {json.dumps(s)}\n\n".encode()
                    self.wfile.write(msg)
                    self.wfile.flush()
                    time.sleep(30)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/":
            html = """<html><head><title>0dte interpreter</title></head><body style="font-family:monospace;background:#0b111b;color:#edf2fa;padding:24px">
            <h2>0dte interpreter</h2><p>status: %s &middot; updated: %s &middot; spot: %s</p>
            <ul><li><a href="/feed/gamma">/feed/gamma</a></li><li><a href="/feed/flow">/feed/flow</a></li>
            <li><a href="/feed/vanna-charm">/feed/vanna-charm</a></li><li><a href="/feed/iv">/feed/iv</a></li>
            <li><a href="/feed/all">/feed/all</a></li><li><a href="/stream">/stream</a> (SSE)</li></ul></body></html>""" % (
                snap.get("status"), snap.get("updated_at"), snap.get("spot"))
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send({"error": "not found"}, 404)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--poll", type=int, default=30, help="poll interval seconds")
    args = ap.parse_args()

    t = threading.Thread(target=poll_forever, args=(args.poll,), daemon=True)
    t.start()
    # warm the first snapshot before serving
    for _ in range(60):
        with LOCK:
            if SNAPSHOT.get("status") in ("ok", "error"):
                break
        time.sleep(1)

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"0dte interpreter on :{args.port} (poll {args.poll}s)", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
