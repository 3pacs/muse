#!/usr/bin/env python3
"""
Read-only Schwab Trader API client scaffold (prepared 2026-10-13).
NOT run against Schwab yet — Anik's app access request for
"Trader API - Individual" was Submitted 2026-10-13 (Schwab email
17:20 UTC); approval typically takes 1-3 business days, after which
the app shows its App Key / Secret in the Developer Portal.

Credentials come from the environment only (never printed):
  SCHWAB_APP_KEY     — App Key (Client ID) from the portal
  SCHWAB_APP_SECRET  — App Secret from the portal

Flow once the app is "Ready For Use":
  1. SCHWAB_APP_KEY=... SCHWAB_APP_SECRET=... python3 schwab_client.py auth-url
     -> open the printed URL, log in, approve. Browser lands on
        https://127.0.0.1:8182/?code=...  (page won't load; copy URL)
  2. python3 schwab_client.py exchange '<full redirect URL or bare code>'
     -> stores tokens in .schwab_token.json next to this file
        (access token ~30 min, refresh token ~7 days)
  3. python3 schwab_client.py probe
     -> SPY quote + today's options chain sample: contract count and a
        near-ATM contract's bid/ask, volume, OI, delta/gamma/IV — the
        verdict on whether Schwab replaces the current
        3-live-strike + 148-delayed-wing feed.

Read-only by design: this module only calls marketdata GET endpoints.
No order/account endpoints are implemented.
"""

import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date

BASE_AUTH = "https://api.schwabapi.com/v1/oauth"
BASE_MD = "https://api.schwabapi.com/marketdata/v1"
CALLBACK = "https://127.0.0.1:8182"
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".schwab_token.json")


def _basic_auth():
    key = os.environ.get("SCHWAB_APP_KEY")
    secret = os.environ.get("SCHWAB_APP_SECRET")
    if not key or not secret:
        print("No keys in environment. Set SCHWAB_APP_KEY and "
              "SCHWAB_APP_SECRET (from the vault, once the app is "
              "Ready For Use).")
        sys.exit(2)
    return base64.b64encode(f"{key}:{secret}".encode()).decode()


def _post_token(form):
    req = urllib.request.Request(
        f"{BASE_AUTH}/token",
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": f"Basic {_basic_auth()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read().decode())
    tok["_saved_at"] = int(time.time())
    with open(TOKEN_PATH, "w") as f:
        json.dump(tok, f)
    os.chmod(TOKEN_PATH, 0o600)
    return tok


def _load_token():
    if not os.path.exists(TOKEN_PATH):
        print("No token file yet. Run auth-url, approve in the browser, "
              "then exchange the code.")
        sys.exit(2)
    with open(TOKEN_PATH) as f:
        tok = json.load(f)
    age = int(time.time()) - tok.get("_saved_at", 0)
    if age > 25 * 60:  # access tokens live ~30 min; refresh proactively
        tok = _post_token({
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
        })
    return tok["access_token"]


def _get(path, params=None):
    url = f"{BASE_MD}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {_load_token()}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def cmd_auth_url():
    key = os.environ.get("SCHWAB_APP_KEY")
    if not key:
        print("Set SCHWAB_APP_KEY first.")
        sys.exit(2)
    q = urllib.parse.urlencode({"client_id": key, "redirect_uri": CALLBACK})
    print(f"{BASE_AUTH}/authorize?{q}")


def cmd_exchange(arg):
    code = arg
    if "code=" in arg:  # full redirect URL pasted back
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(arg).query)
        code = (qs.get("code") or [""])[0]
    if not code:
        print("Could not find code= in the supplied value.")
        sys.exit(2)
    _post_token({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CALLBACK,
    })
    print("Token stored. Run: python3 schwab_client.py probe")


def cmd_probe():
    today = date.today().isoformat()
    q = _get("/quotes", {"symbols": "SPY"})
    spy = (q.get("SPY") or {}).get("quote") or {}
    print(f"SPY quote: last={spy.get('lastPrice')} "
          f"bid={spy.get('bidPrice')} ask={spy.get('askPrice')}")
    ch = _get("/chains", {
        "symbol": "SPY",
        "fromDate": today,
        "toDate": today,
        "includeUnderlyingQuote": "false",
    })
    calls = ch.get("callExpDateMap") or {}
    puts = ch.get("putExpDateMap") or {}
    n = 0
    sample = None
    spot = spy.get("lastPrice") or 0
    for expmap in list(calls.values()) + list(puts.values()):
        for strike, contracts in expmap.items():
            for c in contracts:
                n += 1
                if sample is None or abs(float(strike) - spot) < abs(
                        float(sample.get("strikePrice", 0)) - spot):
                    sample = c
    if not n:
        print("PARTIAL: chain returned 0 contracts (app may lack the "
              "Market Data Production product, or OPRA entitlement).")
        return
    print(f"PASS chain: {n} contracts for {today}; near-ATM sample "
          f"strike={sample.get('strikePrice')} "
          f"bid={sample.get('bid')} ask={sample.get('ask')} "
          f"volume={sample.get('totalVolume')} "
          f"oi={sample.get('openInterest')} "
          f"delta={sample.get('delta')} gamma={sample.get('gamma')} "
          f"iv={sample.get('volatility')}")
    print("-> Real-time full chain with greeks = the Schwab pipe works; "
          "wire into interpreter.py behind a flag and compare live.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "auth-url":
        cmd_auth_url()
    elif cmd == "exchange" and len(sys.argv) == 3:
        cmd_exchange(sys.argv[2])
    elif cmd == "probe":
        cmd_probe()
    else:
        print("Usage: schwab_client.py auth-url | exchange <url|code> | probe")
        sys.exit(2)


if __name__ == "__main__":
    main()
