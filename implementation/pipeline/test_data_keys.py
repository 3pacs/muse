#!/usr/bin/env python3
"""
One-shot tier test for Anik's existing market-data accounts (prepared
2026-10-13; NOT run — no keys provided yet).

Reads keys from environment variables only (never prints them):
  TRADIER_TOKEN   — Tradier production access token
  MASSIVE_API_KEY — Massive.com (Polygon rebrand) API key

Usage:  TRADIER_TOKEN=... MASSIVE_API_KEY=... python3 test_data_keys.py

What it settles, per provider:
  Tradier — does the account return a REAL-TIME SPY options chain with
            per-strike greeks + bid/ask + OI? (Schwab-class chain; the
            free pipe that would replace the 3-live + 148-delayed mix.)
            Also reports profile/account status (funded or not).
  Massive — does the key's tier include the options chain snapshot
            (OI + greeks + quotes; Options Starter and up), and do
            options trades/quotes endpoints answer (tick tape for
            signing prints buyer- vs seller-initiated)?

Exit lines are plain PASS/PARTIAL/FAIL summaries per provider; raw field
names are printed for a few sample contracts, never key material.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date, timedelta


def get(url, token, timeout=15):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "stepdad-keytest/1.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def next_expiry(today=None):
    """SPY has daily expiries on trading days; walk forward to a weekday."""
    d = today or date.today()
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def test_tradier(token):
    print("== Tradier ==")
    try:
        _, prof = get("https://api.tradier.com/v1/user/profile", token)
        p = (prof.get("profile") or {})
        acct = p.get("account") or {}
        if isinstance(acct, list):
            acct = acct[0] if acct else {}
        print(f"  profile ok: name={p.get('name')!r} "
              f"account_type={acct.get('type')!r} status={acct.get('status')!r}")
    except urllib.error.HTTPError as e:
        print(f"  FAIL profile: HTTP {e.code} (token invalid or no access)")
        return
    except Exception as e:
        print(f"  FAIL profile: {e}")
        return
    exp = next_expiry()
    url = ("https://api.tradier.com/v1/markets/options/chains"
           f"?symbol=SPY&expiration={exp}&greeks=true")
    try:
        _, chain = get(url, token)
        opts = ((chain.get("options") or {}).get("option")) or []
        if isinstance(opts, dict):
            opts = [opts]
        if not opts:
            print(f"  PARTIAL: chain for {exp} returned 0 contracts "
                  "(wrong expiry or market-data not entitled)")
            return
        near = min(opts, key=lambda o: abs((o.get("strike") or 0) - 777))
        greeks = near.get("greeks") or {}
        print(f"  PASS chain: {len(opts)} contracts for {exp}; sample near-ATM "
              f"strike={near.get('strike')} bid={near.get('bid')} "
              f"ask={near.get('ask')} volume={near.get('volume')} "
              f"oi={near.get('open_interest')} "
              f"greeks_present={bool(greeks)} delta={greeks.get('delta')} "
              f"gamma={greeks.get('gamma')} iv={greeks.get('mid_iv')}")
        print("  -> Real-time chain with greeks = Schwab-class pipe, $0.")
    except urllib.error.HTTPError as e:
        print(f"  FAIL chain: HTTP {e.code}")
    except Exception as e:
        print(f"  FAIL chain: {e}")


def test_massive(key):
    print("== Massive (Polygon) ==")
    try:
        _, st = get("https://api.massive.com/v1/marketstatus/now", key)
        print(f"  marketstatus ok: {st.get('market')!r} "
              f"server_time={st.get('serverTime')!r}")
    except urllib.error.HTTPError as e:
        print(f"  FAIL marketstatus: HTTP {e.code} (key invalid)")
        return
    except Exception as e:
        print(f"  FAIL marketstatus: {e}")
        return
    exp = next_expiry()
    url = ("https://api.massive.com/v3/snapshot/options/SPY"
           f"?expiration_date={exp}&limit=10")
    try:
        _, snap = get(url, key)
        res = snap.get("results") or []
        if not res:
            print("  PARTIAL: chain snapshot returned 0 results "
                  "(below Options Starter, or expiry filter mismatch)")
            return
        r0 = res[0]
        det = r0.get("details") or {}
        print(f"  PASS chain snapshot: sample contract={det.get('ticker')} "
              f"oi={r0.get('open_interest')} "
              f"greeks={bool(r0.get('greeks'))} "
              f"iv={r0.get('implied_volatility')} "
              f"last_quote={bool(r0.get('last_quote'))} "
              f"last_trade={bool(r0.get('last_trade'))}")
        ticker = det.get("ticker")
        if ticker:
            try:
                _, tr = get(f"https://api.massive.com/v3/trades/{ticker}?limit=5", key)
                n = len(tr.get("results") or [])
                print(f"  trades endpoint: {n} prints returned "
                      f"({'tick tape AVAILABLE' if n else 'answers but empty'})")
            except urllib.error.HTTPError as e:
                print(f"  trades endpoint: HTTP {e.code} (not on this tier)")
            try:
                _, qu = get(f"https://api.massive.com/v3/quotes/{ticker}?limit=5", key)
                n = len(qu.get("results") or [])
                print(f"  quotes endpoint: {n} NBBO quotes returned "
                      f"({'NBBO AVAILABLE — prints can be signed' if n else 'answers but empty'})")
            except urllib.error.HTTPError as e:
                print(f"  quotes endpoint: HTTP {e.code} (not on this tier)")
    except urllib.error.HTTPError as e:
        print(f"  FAIL chain snapshot: HTTP {e.code} "
              "(likely below Options Starter)")
    except Exception as e:
        print(f"  FAIL chain snapshot: {e}")


def main():
    ran = False
    t = os.environ.get("TRADIER_TOKEN")
    m = os.environ.get("MASSIVE_API_KEY")
    if t:
        test_tradier(t)
        ran = True
    if m:
        test_massive(m)
        ran = True
    if not ran:
        print("No keys in environment. Set TRADIER_TOKEN and/or MASSIVE_API_KEY.")
        sys.exit(2)


if __name__ == "__main__":
    main()
