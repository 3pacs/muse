#!/usr/bin/env python3
"""Independent offline server-port contract checks. Run: helper EXPORT_ROOT OUT_DIR.

EXPORT_ROOT contains stopgap-20261022-muse and stopgap-20261022-dashboard at bb1763ff.
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
root, out = map(Path, sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
schema_path = root / 'stopgap-20261022-muse/contract-rev3/feed_all.schema.json'
capture = root / 'stopgap-20261022-dashboard/tests/fixture-feed-all.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(schema_path) == '43ede0de4c5cdee398e6bced05a170797903507baed64a7670afa614b0ce8b21'
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
receipt = dict(local_export_commit='bb1763ff98f44ab6ed2de41fb05cbe9f194d7302',
               schema_sha256=sha(schema_path), capture_sha256=sha(capture), helper_sha256=sha(Path(__file__)),
               mode='Offline schema checks on retained capture and labelled mutations; no producer/model/runtime execution.',
               passed=sum(c['passed'] for c in checks), total=len(checks), checks=checks)
(out / 'independent-contract.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:receipt[k] for k in ['passed','total','schema_sha256']}))
for c in checks:
    if not c['passed']: print('FAIL', c['name'], 'accepted=', c['actual_valid'])
sys.exit(0 if receipt['passed'] == receipt['total'] else 1)
