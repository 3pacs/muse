"""Cboe delayed SPY option chain -> the legacy `/api/contracts` shape the Muse 0DTE interpreter consumes.

Provider: https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json (public, ~15 min delayed; redirects to
cdn-api.cboe.com — urllib follows it). The same provider gex-watch's sectors.py has used since September.
Honest labelling: every payload carries provider "cboe_delayed", delay "~15min" and the provider's own timestamp as
`as_of` (the feed's "timestamp" is UTC: observed 22:59:59 at 23:00Z). No field is invented; absent values stay None.
Stdlib only; no retries here (the caller's loop retries on its own cadence); never raises into the server loop
except through the caller's try/except.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone

URL = 'https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json'
SYMBOL_RE = re.compile(r'^(SPY)(\d{6})([CP])(\d{8})$')
MAX_BYTES = 40 * 1024 * 1024


def _num(v):
    try:
        if v is None or isinstance(v, bool):
            return None
        x = float(v)
        return x if x == x and abs(x) != float('inf') else None
    except (TypeError, ValueError):
        return None


def _int(v):
    x = _num(v)
    return int(x) if x is not None else None


def parse_timestamp(ts):
    """'2026-10-22 22:59:59' (provider, UTC) -> ISO 8601 UTC string, or None."""
    if type(ts) is not str:
        return None
    try:
        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def map_payload(raw):
    """Provider JSON -> {'provider','delay','as_of','symbol','current_price','contracts':[legacy rows]}."""
    data = raw.get('data') if isinstance(raw, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get('options'), list):
        raise ValueError('cboe payload shape')
    as_of = parse_timestamp(raw.get('timestamp'))
    rows = []
    for o in data['options']:
        if not isinstance(o, dict):
            continue
        m = SYMBOL_RE.match(str(o.get('option', '')))
        if not m:
            continue
        yymmdd, side, strike8 = m.group(2), m.group(3), m.group(4)
        try:
            expiry = datetime.strptime(yymmdd, '%y%m%d').date().isoformat()
        except ValueError:
            continue
        rows.append({
            'symbol': o['option'], 'strike': int(strike8) / 1000.0, 'expiry': expiry, 'side': side,
            'bid': _num(o.get('bid')), 'ask': _num(o.get('ask')),
            'bid_size': _int(o.get('bid_size')), 'ask_size': _int(o.get('ask_size')),
            'volume': _num(o.get('volume')), 'open_interest': _num(o.get('open_interest')),
            'delta': _num(o.get('delta')), 'gamma': _num(o.get('gamma')), 'theta': _num(o.get('theta')),
            'vega': _num(o.get('vega')), 'iv': _num(o.get('iv')),
            'last': _num(o.get('last_trade_price')), 'last_trade_time': o.get('last_trade_time'),
            'as_of': as_of,
        })
    return {'provider': 'cboe_delayed', 'delay': '~15min', 'as_of': as_of, 'symbol': 'SPY',
            'current_price': _num(data.get('current_price')), 'contracts': rows,
            'received_at': datetime.now(timezone.utc).isoformat(),
            'note': 'Cboe public delayed quotes; not executable; OI vintage per provider; wings/strikes beyond the RTD subscription come only from here.'}


def fetch(timeout=25):
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError('cboe payload too large')
    return map_payload(json.loads(body.decode('utf-8')))
