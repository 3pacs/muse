#!/usr/bin/env python3
"""Verify LIVE-G1-R2: original 10 + 12 boundary checks."""
import contextlib
import datetime as dt
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'adapter', Path.home() / 'workspace/live-g1/live_g1_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

db = types.ModuleType('accepted_tape_db')
exec(compile(open('/tmp/accepted_tape_db.py').read(), 'tape_db.py', 'exec'), db.__dict__)

NOW = dt.datetime(2026, 10, 5, 15, 0, tzinfo=dt.timezone.utc)
adapter._NOW_OVERRIDE = NOW

results = []
def record(name, passed, observed=None):
    results.append((name, bool(passed)))
    print(f"{'PASS' if passed else 'FAIL'} {name}")
    if not passed and observed is not None:
        print(f"  observed: {json.dumps(observed, default=str)[:250]}")

@contextlib.contextmanager
def context(rec=None, interp_ok=False):
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
        adapter.check_interpreter = lambda: (interp_ok, 'test')
        yield p, con
        con.close()

base = {
    'ts': '2026-10-05T14:59:00+00:00', 'expiry': '2026-10-05', 'spot': 765.0,
    'quote_as_of': '2026-10-05T14:30:00Z', 'nasdaq_as_of': '2026-10-05T14:40:00Z',
    'src_mix': '0 rtd + 10 nasdaq_delayed', 'call_oi': 1234, 'put_oi': 0,
    'exp_move_dollars': 4.5, 'gex_formula': 'v2',
    'gex_units': 'USD millions per 1% spot move',
}

print("=== Original 10 ===")
with context(base):
    s = adapter.get_snapshot()['fields']
    record('preserve_existing_quote_observation_clock', s['spot']['source_at'] == base['quote_as_of'], s['spot'])
    record('receipt_clock_missing_stays_unknown', s['spot']['received_at'] is None, s['spot'])
    record('source_mix_not_promoted_to_rtd_live', 'RTD' not in s['spot']['source'], s['spot'])
    record('unknown_oi_vintage_not_inferred_from_record_date', s['call_oi'].get('oi_vintage') is None, s['call_oi'])
    record('accepted_expected_move_column_mapped', s['expected_move']['value'] == 4.5, s['expected_move'])
    record('zero_oi_preserved_control', s['put_oi']['value'] == 0, s['put_oi'])
with context(dict(base, ts='2026-10-02T20:00:00+00:00')):
    st = adapter.get_status()
    record('disconnected_old_data_not_fresh_during_market_hours', st['data_vintage']['stale'] is True, st['data_vintage'])
bad = [adapter.wrap_field(765.0, 'USD', 'unknown', sa, None)
       for sa in [None, 'bad-clock', '2026-10-05T14:59:00', '2026-10-06T15:00:00Z']]
record('unknown_invalid_naive_future_clocks_not_fresh', all(f['stale'] or f['unavailable'] for f in bad), bad)
with context() as (p, con):
    adapter.GEX_HISTORY.write_text(json.dumps({'ts': base['ts'], 'expiry': base['expiry'], 'spot': 765,
        'gex_m': {'765.0': .02, '770.0': 0}, 'gex_formula': 'v2', 'gex_units': base['gex_units']}) + '\n')
    hm = adapter.get_heatmap()
    record('accepted_gex_history_map_becomes_real_cells',
           len(hm['cells']) == 2 and all(c.get('recorded_at') == base['ts'] for c in hm['cells']), hm)
with tempfile.TemporaryDirectory() as td:
    adapter.TAPE_DB = Path(td) / 'missing.db'
    record('missing_database_unavailable_control', adapter.get_snapshot().get('unavailable') is True)

print("\n=== R2 12 boundaries ===")
# 1. Missing quote clock stays unknown
with context({**base, 'quote_as_of': None}):
    s = adapter.get_snapshot()['fields']['spot']
    record('r2_missing_quote_clock_stays_unknown', s['source_at'] is None and s['stale'] is True, s)
# 2. Missing chain clock stays unknown
with context({**base, 'nasdaq_as_of': None}):
    s = adapter.get_snapshot()['fields']['call_oi']
    record('r2_missing_chain_clock_stays_unknown', s['source_at'] is None and s['stale'] is True, s)
# 3. Reachable + old data stays stale
with context(dict(base, ts='2026-10-02T20:00:00+00:00'), interp_ok=True):
    st = adapter.get_status()
    record('r2_reachable_old_data_stays_stale', st['data_vintage']['stale'] is True, st['data_vintage'])
# 4. Reachable + empty DB is not fresh
with context(None, interp_ok=True):
    st = adapter.get_status()
    record('r2_reachable_empty_db_not_fresh', st['data_vintage']['stale'] is True, st['data_vintage'])
# 5. Reachable + future data is not fresh
with context(dict(base, ts='2026-10-06T15:00:00+00:00'), interp_ok=True):
    st = adapter.get_status()
    record('r2_reachable_future_data_not_fresh', st['data_vintage']['stale'] is True, st['data_vintage'])
# 6. Disconnected + recent data = stale
recent = dict(base, ts='2026-10-05T14:59:00+00:00')  # 1 min old at 15:00
with context(recent, interp_ok=False):
    st = adapter.get_status()
    record('r2_disconnected_recent_data_stale', st['data_vintage']['stale'] is True, st['data_vintage'])
# 7. Reconnect without newer data does not clear staleness
old_rec = dict(base, ts='2026-10-02T20:00:00+00:00')
with context(old_rec, interp_ok=False):
    st1 = adapter.get_status()
with context(old_rec, interp_ok=True):
    st2 = adapter.get_status()
record('r2_reconnect_without_new_data_stays_stale',
       st1['data_vintage']['stale'] is True and st2['data_vintage']['stale'] is True,
       {'disconnected': st1['data_vintage'], 'reconnected': st2['data_vintage']})
# 8. Heatmap retains expiry
with context() as (p, con):
    adapter.GEX_HISTORY.write_text(
        json.dumps({'ts': '2026-10-05T14:00:00+00:00', 'expiry': '2026-10-05', 'gex_m': {'765.0': .02}, 'gex_formula': 'v2'}) + '\n' +
        json.dumps({'ts': '2026-10-05T14:00:00+00:00', 'expiry': '2026-10-06', 'gex_m': {'765.0': .03}, 'gex_formula': 'v2'}) + '\n')
    hm = adapter.get_heatmap()
    expiries = {c.get('expiry') for c in hm['cells']}
    record('r2_heatmap_retains_expiry', expiries == {'2026-10-05', '2026-10-06'}, hm['cells'][:2])
# 9. Unknown RTD counts never claim RTD
with context({**base, 'src_mix': 'None rtd + None nasdaq_delayed'}):
    s = adapter.get_snapshot()['fields']['spot']
    record('r2_unknown_rtd_counts_not_rtd', 'RTD' not in s['source'], s)
# 10. Valid recent connected status (control, should pass)
with context(recent, interp_ok=True):
    st = adapter.get_status()
    record('r2_valid_recent_connected_may_be_fresh', st['data_vintage']['stale'] is False, st['data_vintage'])
# 11. Genuinely newer observation permits recovery (control)
with context(dict(base, ts='2026-10-05T14:59:30+00:00'), interp_ok=True):
    st = adapter.get_status()
    s = adapter.get_snapshot()['fields']['spot']
    record('r2_newer_observation_permits_recovery',
           st['data_vintage']['stale'] is False and s['source_at'] == base['quote_as_of'],
           {'vintage': st['data_vintage'], 'spot': s})
# 12. Zero GEX preserved (control)
with context() as (p, con):
    adapter.GEX_HISTORY.write_text(json.dumps({'ts': base['ts'], 'expiry': '2026-10-05',
        'gex_m': {'770.0': 0}, 'gex_formula': 'v2', 'gex_units': 'USD millions per 1% spot move'}) + '\n')
    hm = adapter.get_heatmap()
    record('r2_zero_gex_preserved', len(hm['cells']) == 1 and hm['cells'][0]['gex'] == 0
           and hm['cells'][0]['formula'] == 'v2', hm['cells'])

adapter._NOW_OVERRIDE = None
passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} pass")
sys.exit(0 if passed == len(results) else 1)
