"""Offline LIVE-G1 compatibility checks; synthetic cases, not real captures."""
from pathlib import Path
import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', required=True, type=Path)
parser.add_argument('--backend-repo', required=True, type=Path)
parser.add_argument('--candidate-pin', default='2b38e8848ae32fdc5f2f854d835975a5cfca4ab0')
parser.add_argument('--receipt', default='live-g1-contract-results.json', type=Path)
args = parser.parse_args()
SOURCE_ROOT = args.source_root.resolve()
BACKEND_REPO = args.backend_repo.resolve()
SHA = args.candidate_pin
BASE = '8649ad541cb794d0d26cdc4bb2f18ccd1ad0a7ac'
def blocked(*args, **kwargs):
    raise AssertionError('Network prohibited in offline review')
socket.socket.connect = blocked
socket.create_connection = blocked
urllib.request.urlopen = blocked

spec = importlib.util.spec_from_file_location('actual_live_adapter', SOURCE_ROOT/'live-g1/live_g1_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
source = subprocess.check_output(['git','-C',str(BACKEND_REPO),'show',BASE+':tape_db.py'],text=True)
db = type(sys)('accepted_tape_db')
exec(compile(source,'immutable-tape_db.py','exec'),db.__dict__)
NOW = dt.datetime(2026,10,5,15,0,tzinfo=dt.timezone.utc)
class Clock(dt.datetime):
    @classmethod
    def now(cls,tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
adapter.datetime = Clock
adapter.check_interpreter = lambda: (False, 'disconnected synthetic test boundary')
results = []
def record(name, passed, observed, expected):
    results.append({'name':name,'pass_contract':bool(passed),'observed':observed,'expected':expected})

@contextlib.contextmanager
def context(rec=None):
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)
        adapter.TAPE_DB=p/'tape.db';adapter.JOURNAL=p/'maxpain_history.jsonl';adapter.GEX_HISTORY=p/'gex_history.jsonl'
        db.HIDDEN=str(p);db.DB_PATH=str(adapter.TAPE_DB)
        con=db.connect();db.init_db(con)
        if rec is not None:db.insert_snapshot(rec,con)
        yield p,con
        con.close()

base={'ts':'2026-10-05T14:59:00+00:00','expiry':'2026-10-05','spot':765.0,
      'quote_as_of':'2026-10-05T14:30:00Z','nasdaq_as_of':'2026-10-05T14:40:00Z',
      'src_mix':'0 rtd + 10 nasdaq_delayed','call_oi':1234,'put_oi':0,
      'exp_move_dollars':4.5,'gex_formula':'v2','gex_units':'USD millions per 1% spot move'}
with context(base):
    snapshot=adapter.get_snapshot();spot=snapshot['fields']['spot']
    record('preserve_existing_quote_observation_clock',spot['source_at']==base['quote_as_of'],spot,
           'use available quote_as_of; snapshot ts is not the quote source clock')
    record('receipt_clock_missing_stays_unknown',spot['received_at'] is None,spot,
           'SQLite row has no receipt clock; unknown must not be fabricated from event ts')
    record('source_mix_not_promoted_to_rtd_live','RTD' not in spot['source'],spot,
           'zero RTD plus delayed source must not be labeled an RTD observation')
    oi=snapshot['fields']['call_oi']
    record('unknown_oi_vintage_not_inferred_from_record_date',oi.get('oi_vintage') is None,oi,
           'no OI as-of/vintage exists in this input; preserve unknown, never invent settlement date')
    move=snapshot['fields']['expected_move']
    record('accepted_expected_move_column_mapped',move['value']==4.5,move,
           'accepted backend exp_move_dollars=4.5 survives adapter mapping')
    record('zero_oi_preserved_control',snapshot['fields']['put_oi']['value']==0,
           snapshot['fields']['put_oi'],'zero remains a real value rather than missing')

old=dict(base,ts='2026-10-02T20:00:00+00:00')
with context(old):
    status=adapter.get_status()
    record('disconnected_old_data_not_fresh_during_market_hours',
           status['data_vintage']['stale'] is True,status,
           'disconnection and old observation dominate wall-clock market-open state')

bad=[]
for source_at in [None,'bad-clock','2026-10-05T14:59:00','2026-10-06T15:00:00Z']:
    field=adapter.wrap_field(765.0,'USD','unknown',source_at,None)
    bad.append(field)
record('unknown_invalid_naive_future_clocks_not_fresh',
       all(f['stale'] or f['unavailable'] for f in bad),bad,
       'bad/missing/future clocks carry explicit unknown or unavailable/stale quality, never fresh')

with context() as (p,con):
    row={'ts':base['ts'],'expiry':base['expiry'],'spot':765,'gex_m':{'765.0':.02,'770.0':0},
         'gex_formula':'v2','gex_units':base['gex_units']}
    adapter.GEX_HISTORY.write_text(json.dumps(row)+'\n')
    heatmap=adapter.get_heatmap();cells=heatmap['cells']
    record('accepted_gex_history_map_becomes_real_cells',
           len(cells)==2 and all(c.get('recorded_at')==base['ts'] and c.get('strike') is not None
                                and c.get('gex') is not None for c in cells),heatmap,
           'accepted ts/expiry/gex_m format becomes two valued cells with zero preserved')

with tempfile.TemporaryDirectory() as td:
    adapter.TAPE_DB=Path(td)/'missing.db'
    missing=adapter.get_snapshot()
    record('missing_database_unavailable_control',missing.get('unavailable') is True,missing,
           'missing database is reported unavailable')

receipt={'source_head':SHA,'accepted_backend_schema':BASE,'synthetic_contract_cases_only':True,
         'real_capture_claim':False,'network_blocked':True,'results':results,
         'passes':sum(r['pass_contract'] for r in results),
         'failures':sum(not r['pass_contract'] for r in results),
         'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))

raise SystemExit(0 if receipt['failures'] == 0 else 1)
