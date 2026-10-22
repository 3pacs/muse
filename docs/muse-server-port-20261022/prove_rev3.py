#!/usr/bin/env python3
"""Offline proof of the rev3 /feed/all contract. No sockets, no provider, no DB, no producer import.

  python3 prove_rev3.py <captured-ok-snapshot.json> <out-dir>

Checks: meta-schema validity; the REAL captured ok snapshot (server port, Cboe chain, RTD quote) is admitted;
the three rev2 coverage gaps now pass (nasdaq as_of null; rtd provider with as_of null; alternate vendor key);
public-fallback and no-quote provenance; rev2 status variants still admitted; and rejections (unknown status,
missing nasdaq, no chain provider, numeric clock, timezone-less clock, public quote labelled realtime, rtd key
alongside cboe_delayed, extra key in a chain entry). Writes <out-dir>/rev3-receipt.json with input/output hashes.
"""
import copy, hashlib, json, socket, sys
from pathlib import Path
from jsonschema import Draft202012Validator

def deny(*a, **k): raise AssertionError('OFFLINE_ONLY')
socket.socket.connect = deny; socket.create_connection = deny

HERE = Path(__file__).resolve().parent
schema_path = HERE / 'feed_all.schema.json'
capture_path, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
schema = json.loads(schema_path.read_text())
Draft202012Validator.check_schema(schema)
V = Draft202012Validator(schema)
OK = Draft202012Validator({'$ref': '#/$defs/ok', '$defs': schema['$defs']})  # ok-variant errors, with the root $defs in scope
checks = []
def rec(name, passed, detail=None): checks.append({'name': name, 'pass': bool(passed), 'detail': detail}); print(('PASS ' if passed else 'FAIL ') + name)
def errs(doc): return [{'path': '/'.join(map(str, e.absolute_path)), 'message': e.message[:160]} for e in OK.iter_errors(doc)]

cap = json.loads(capture_path.read_text())
assert cap['status'] == 'ok'
rec('meta-schema-valid', True)
rec('captured-real-ok-snapshot-admitted', V.is_valid(cap), {'sources_keys': sorted(cap['sources']), 'errors': errs(cap)})

# rev2 coverage gap 1: optional Nasdaq acquisition unavailable -> as_of null, n_strikes 0
g1 = copy.deepcopy(cap); g1['sources']['nasdaq'].update(as_of=None, n_strikes=0, stale=False); g1['n_strikes_nasdaq_delayed'] = 0
rec('gap1-nasdaq-as_of-null-admitted', V.is_valid(g1), errs(g1))
# rev2 coverage gap 2: original producer shape — rtd chain with unknown clock, no quote block
g2 = copy.deepcopy(cap); g2['sources'] = {'rtd': {'as_of': None, 'delay': 'realtime', 'n_strikes': 3}, 'nasdaq': cap['sources']['nasdaq']}; g2['n_strikes_rtd_live'] = 3
rec('gap2-rtd-as_of-null-no-quote-block-admitted', V.is_valid(g2), errs(g2))
# rev2 coverage gap 3: alternate declared provider key
g3 = copy.deepcopy(cap); src = g3['sources'].pop('cboe_delayed'); g3['sources']['vendor_delayed'] = src
rec('gap3-alternate-provider-key-admitted', V.is_valid(g3), errs(g3))
# quote provenance variants
pf = copy.deepcopy(cap); pf['sources']['quote'] = {'source': 'public_price', 'delay': 'latency-unverified', 'as_of': cap['quote_as_of'], 'clock': 'provider-as-of'}
rec('public-fallback-quote-admitted', V.is_valid(pf), errs(pf))
nq = copy.deepcopy(cap); nq['sources']['quote'] = {'source': None, 'delay': None, 'as_of': None}
rec('no-quote-provenance-shape-admitted', V.is_valid(nq), errs(nq))
# rev2 status variants (synthetic, labelled) still admitted
for name, doc in [('error-sparse', {'status': 'error', 'error': 'timeout', 'updated_at': cap['updated_at']}),
                  ('error-no-quote', {'status': 'error', 'error': 'no quote in feed (spot=0)', 'updated_at': cap['updated_at'], 'market_open': False, 'spot': 0, 'expiry': cap['expiry']}),
                  ('quarantined', {'status': 'quarantined', 'quarantine_reason': 'quote_as_of in the future', 'updated_at': cap['updated_at'], 'market_open': False, 'quote_as_of': cap['updated_at']}),
                  ('starting', {'status': 'starting', 'updated_at': None})]:
    rec('variant-' + name + '-admitted', V.is_valid(doc))
# rejections
def reject(name, mutate):
    d = copy.deepcopy(cap); mutate(d); rec('reject-' + name, not V.is_valid(d), errs(d)[:2])
reject('unknown-status', lambda d: d.update(status='maybe'))
reject('missing-nasdaq', lambda d: d['sources'].pop('nasdaq'))
reject('no-chain-provider', lambda d: d['sources'].pop('cboe_delayed'))
reject('numeric-clock', lambda d: d['sources']['cboe_delayed'].update(as_of=1792700000))
reject('timezone-less-clock', lambda d: d['sources']['cboe_delayed'].update(as_of='2026-10-22T23:28:01'))
reject('public-quote-labelled-realtime', lambda d: d['sources'].update(quote={'source': 'public_price', 'delay': 'realtime', 'as_of': d['quote_as_of'], 'clock': 'provider-as-of'}))
reject('two-chain-providers', lambda d: d['sources'].update(rtd={'as_of': None, 'delay': 'realtime', 'n_strikes': 3}))
reject('extra-key-in-chain-entry', lambda d: d['sources']['cboe_delayed'].update(fresh=True))
reject('spot-zero-in-ok', lambda d: d.update(spot=0))
reject('fabricated-string-net-gex', lambda d: d['gamma']['by_strike'][0].update(net_gex_m='0'))

receipt = {'schema': 'feed_all.schema.json', 'schema_sha256': sha(schema_path), 'captured_snapshot_sha256': sha(capture_path),
           'helper_sha256': sha(Path(__file__)), 'mode': 'offline; sockets denied; captured real ok snapshot + labelled synthetic variants; no producer import, no provider, no DB',
           'passed': sum(c['pass'] for c in checks), 'total': len(checks), 'checks': checks}
(out / 'rev3-receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
print('SUMMARY passed=%d total=%d schema=%s' % (receipt['passed'], receipt['total'], receipt['schema_sha256'][:16]))
sys.exit(0 if receipt['passed'] == receipt['total'] else 1)
