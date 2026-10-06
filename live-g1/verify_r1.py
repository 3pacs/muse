#!/usr/bin/env python3
"""Replicate the reviewer's LIVE-G1-R1 harness checks against the fixed adapter."""
import contextlib
import datetime as dt
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

# Load adapter
spec = importlib.util.spec_from_file_location(
    'adapter', Path.home() / 'workspace/live-g1/live_g1_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

# Load accepted tape_db from the downloaded file
import types
db = types.ModuleType('accepted_tape_db')
source = open('/tmp/accepted_tape_db.py').read()
exec(compile(source, 'tape_db.py', 'exec'), db.__dict__)

# Mock clock to reviewer's NOW
NOW = dt.datetime(2026, 10, 5, 15, 0, tzinfo=dt.timezone.utc)
adapter._NOW_OVERRIDE = NOW
adapter.check_interpreter = lambda: (False, 'disconnected synthetic test boundary')

results = []
def record(name, passed, observed=None):
    results.append((name, bool(passed)))
    status = "PASS" if passed else "FAIL"
    print(f"{status} {name}")
    if not passed and observed is not None:
        print(f"  observed: {json.dumps(observed, default=str)[:200]}")

@contextlib.contextmanager
def context(rec=None):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        adapter.TAPE_DB = p / 'tape.db'
        adapter.JOURNAL = p / 'maxpain_history.jsonl'
        adapter.GEX_HISTORY = p / 'gex_history.jsonl'
        db.HIDDEN = str(p)
        db.DB_PATH = str(adapter.TAPE_DB)
        con = db.connect()
        db.init_db(con)
        if rec is not None:
            db.insert_snapshot(rec, con)
        yield p, con
        con.close()

base = {
    'ts': '2026-10-05T14:59:00+00:00', 'expiry': '2026-10-05', 'spot': 765.0,
    'quote_as_of': '2026-10-05T14:30:00Z', 'nasdaq_as_of': '2026-10-05T14:40:00Z',
    'src_mix': '0 rtd + 10 nasdaq_delayed', 'call_oi': 1234, 'put_oi': 0,
    'exp_move_dollars': 4.5, 'gex_formula': 'v2',
    'gex_units': 'USD millions per 1% spot move',
}

with context(base):
    snapshot = adapter.get_snapshot()
    spot = snapshot['fields']['spot']
    record('preserve_existing_quote_observation_clock',
           spot['source_at'] == base['quote_as_of'], spot)
    record('receipt_clock_missing_stays_unknown',
           spot['received_at'] is None, spot)
    record('source_mix_not_promoted_to_rtd_live',
           'RTD' not in spot['source'], spot)
    oi = snapshot['fields']['call_oi']
    record('unknown_oi_vintage_not_inferred_from_record_date',
           oi.get('oi_vintage') is None, oi)
    move = snapshot['fields']['expected_move']
    record('accepted_expected_move_column_mapped',
           move['value'] == 4.5, move)
    record('zero_oi_preserved_control',
           snapshot['fields']['put_oi']['value'] == 0,
           snapshot['fields']['put_oi'])

old = dict(base, ts='2026-10-02T20:00:00+00:00')
with context(old):
    status = adapter.get_status()
    record('disconnected_old_data_not_fresh_during_market_hours',
           status['data_vintage']['stale'] is True, status['data_vintage'])

bad = []
for source_at in [None, 'bad-clock', '2026-10-05T14:59:00', '2026-10-06T15:00:00Z']:
    field = adapter.wrap_field(765.0, 'USD', 'unknown', source_at, None)
    bad.append(field)
record('unknown_invalid_naive_future_clocks_not_fresh',
       all(f['stale'] or f['unavailable'] for f in bad), bad)

with context() as (p, con):
    row = {'ts': base['ts'], 'expiry': base['expiry'], 'spot': 765,
           'gex_m': {'765.0': .02, '770.0': 0},
           'gex_formula': 'v2', 'gex_units': base['gex_units']}
    adapter.GEX_HISTORY.write_text(json.dumps(row) + '\n')
    heatmap = adapter.get_heatmap()
    cells = heatmap['cells']
    record('accepted_gex_history_map_becomes_real_cells',
           len(cells) == 2 and all(
               c.get('recorded_at') == base['ts'] and c.get('strike') is not None
               and c.get('gex') is not None for c in cells),
           heatmap)

with tempfile.TemporaryDirectory() as td:
    adapter.TAPE_DB = Path(td) / 'missing.db'
    missing = adapter.get_snapshot()
    record('missing_database_unavailable_control',
           missing.get('unavailable') is True, missing)

# Reset override
adapter._NOW_OVERRIDE = None

passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"\n{passed}/{len(results)} pass")
sys.exit(0 if failed == 0 else 1)
