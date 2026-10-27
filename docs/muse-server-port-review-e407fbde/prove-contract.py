#!/usr/bin/env python3
"""Independent offline server-port contract checks. Run: helper PACKET_DIR CAPTURE OUT_DIR.

PACKET_DIR is docs/muse-server-port-20261022 at e407fbde; CAPTURE is the retained f33765ac input.
No producer import, model execution, provider, server, credentials or database.
"""
import copy
import hashlib
import json
import socket
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

def deny(*a, **k):
    raise AssertionError('OFFLINE_ONLY')
socket.socket.connect = deny
socket.create_connection = deny
root, capture, out = map(Path, sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
schema_path = root / 'feed_all.schema.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(schema_path) == '5a93b50ad13c34d3c9edd922df31e119ae37ae40f773fe15f4479cb92466092d'
assert sha(capture) == 'f33765ac82e290de0b10743eaba124e7e2672c0c53005cd92c6e90e7d6a40fec'
schema = json.loads(schema_path.read_text())
Draft202012Validator.check_schema(schema)
v = Draft202012Validator(schema)
cap = json.loads(capture.read_text())
checks = []
def rec(name, doc, expected_valid):
    actual = v.is_valid(doc)
    checks.append(dict(name=name, expected_valid=expected_valid, actual_valid=actual,
                       passed=actual == expected_valid,
                       sources=doc.get('sources'),
                       errors=[e.message[:120] for e in v.iter_errors(doc)][:2]))
def variant():
    return copy.deepcopy(cap)
rec('captured-server-port-envelope', cap, True)
d = variant(); d['sources']['nasdaq']['as_of'] = None
rec('unknown-nasdaq-clock', d, True)
d = variant(); d['sources']['vendor_delayed'] = d['sources'].pop('cboe_delayed')
rec('alternate-chain-provider', d, True)
d = variant(); d['sources'].pop('quote')
rec('single-chain-without-quote', d, True)
d['sources']['rtd'] = {'as_of': None, 'delay': 'realtime', 'n_strikes': 3}
rec('reject-two-chain-providers-without-quote', d, False)
d = variant(); d['sources']['rtd'] = {'as_of': None, 'delay': 'realtime', 'n_strikes': 3}
rec('reject-two-chain-providers-with-quote', d, False)
d = variant(); d['sources'].pop('cboe_delayed')
rec('reject-no-chain-provider', d, False)
d = variant(); d['sources']['quote'] = {'source':'public_price', 'delay':'latency-unverified', 'as_of':None, 'clock':'provider-as-of'}
rec('public-quote-provider-clock-unknown-time', d, True)
d = variant(); d['sources']['quote'] = {'source':'public_price', 'delay':'latency-unverified', 'as_of':None, 'clock':'collector-receipt'}
rec('reject-public-quote-mislabelled-collector-clock', d, False)
d = variant(); d['sources']['quote'] = {'source':None, 'delay':None, 'as_of':None}
rec('unknown-quote-provenance-shape-only', d, True)
receipt = dict(packet_commit='e407fbde8cbb51147e5104863e9dd80a44ead747',
               schema_sha256=sha(schema_path), capture_sha256=sha(capture), helper_sha256=sha(Path(__file__)),
               mode='Offline schema checks on retained capture and labelled mutations; no producer/model/runtime execution.',
               passed=sum(c['passed'] for c in checks), total=len(checks), checks=checks)
(out / 'independent-contract.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:receipt[k] for k in ['passed','total','schema_sha256']}))
for c in checks:
    if not c['passed']: print('FAIL', c['name'], 'accepted=', c['actual_valid'])
sys.exit(0 if receipt['passed'] == receipt['total'] else 1)
