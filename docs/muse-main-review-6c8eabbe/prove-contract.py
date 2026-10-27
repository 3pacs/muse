"""Pinned artifact/schema/clock review. Never imports the producer module or invokes its I/O.
Usage: python3 prove-contract.py PACKET_DIR OUTPUT_JSON
Requires the already-installed jsonschema package; no dependency installation/network.
"""
import ast,copy,hashlib,importlib.metadata,json,sys,threading
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from jsonschema import Draft202012Validator,SchemaError
base,out=map(Path,sys.argv[1:]);out.parent.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=base/'interpreter.py';schemafile=base/'feed_all.schema.json'
assert sha(source)=='b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e'
assert sha(schemafile)=='19513e2067245b2b3bc99c0b50eebb56b86e45117828b62441eb2dfd50f067da'
manifest=json.loads((base/'captures.json').read_text());schema=json.loads(schemafile.read_text());capture=json.loads((base/'envelope-ok-afterclose-20261020.json').read_text())
bindings=[]
for e in [manifest['source_pin'],manifest['schema'],*manifest['captures']]:
    if e.get('file'):bindings.append({'path':e['file'],'match':sha(base/e['file'])==e['sha256']})
observations=[]
def record(name,passed,actual):observations.append({'name':name,'pass':bool(passed),'actual':actual})
record('supplied-artifact-hash-bindings',all(x['match'] for x in bindings),bindings)
try:
    Draft202012Validator.check_schema(schema);meta={'valid':True}
except SchemaError as e:
    meta={'valid':False,'path':list(e.path),'message':e.message,'context':[c.message for c in e.context]}
record('declared-2020-12-schema-valid',meta['valid'],meta)
# Deliberately separate diagnostic validation from schema validity: this
# constructor does not check the meta-schema; success is NOT contract acceptance.
validator=Draft202012Validator(schema)
def errors(value):return [{'path':list(e.path),'message':e.message} for e in validator.iter_errors(value)]
record('retained-afterclose-data-diagnostic',not errors(capture),{'errors':errors(capture),'qualification':'Diagnostic only: the schema itself is invalid. Capture is owner-supplied after-close data, not a current runtime observation.'})

# Compile only exact selected function source segments. fetch_json and sleep
# are in-memory stubs. No original imports, module setup, fetch helpers,
# database, web server, thread start, provider or filesystem runtime executes.
text=source.read_text();tree=ast.parse(text)
selected={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['market_open_now','seconds_to_expiry','build_snapshot','poll_forever']}
assert len(selected)==4
fixed=datetime.fromisoformat('2026-10-20T21:29:16.142252+00:00')
class FrozenDateTime(datetime):
    @classmethod
    def now(cls,tz=None):return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
class StopReplay(Exception):pass
stub_calls=[]
def stop_sleep(_):raise StopReplay()
env={'datetime':FrozenDateTime,'timezone':timezone,'ET':ZoneInfo('America/New_York'),'PT':ZoneInfo('America/Los_Angeles'),'YEAR_SECONDS':365.25*24*3600,'STATE_URL':'offline:state','CONTRACTS_URL':'offline:contracts','LOCK':threading.Lock(),'SNAPSHOT':None,'time':SimpleNamespace(sleep=stop_sleep)}
for name,node in selected.items():exec(compile(ast.get_source_segment(text,node),'PINNED_SOURCE:'+name,'exec'),env)
def timeout_fetch(url):stub_calls.append(url);raise TimeoutError('OFFLINE_TIMEOUT')
env['fetch_json']=timeout_fetch
try:env['poll_forever'](30)
except StopReplay:pass
timeout=env['SNAPSHOT']
record('actual-source-timeout-envelope-admitted',not errors(timeout),{'envelope':timeout,'schema_errors':errors(timeout),'qualification':'Exact poll/build source, synthetic in-memory timeout; NOT a retained production failure capture.'})
def quote_fetch(url):
    stub_calls.append(url)
    return {'quote':{'price':0}} if url=='offline:state' else {'contracts':[{'expiry':'2026-10-20','strike':770,'side':'C'}]}
env['fetch_json']=quote_fetch
noquote=env['build_snapshot']()
record('actual-source-no-quote-envelope-admitted',not errors(noquote),{'envelope':noquote,'schema_errors':errors(noquote),'qualification':'Exact source branch, synthetic inputs; no numerical model or provider was run.'})
def future_fetch(url):
    stub_calls.append(url)
    return {'quote':{'price':771.2,'as_of':'2026-10-20T22:00:00+00:00'}} if url=='offline:state' else {'contracts':[]}
env['fetch_json']=future_fetch
future=env['build_snapshot']()
record('actual-source-quarantine-envelope-admitted',not errors(future),{'envelope':future,'schema_errors':errors(future),'qualification':'Exact source branch, synthetic future quote; no actual provider request.'})
putwall=copy.deepcopy(capture);putwall['gamma']['put_wall']=768.0
record('numeric-put-wall-source-variant-admitted',not errors(putwall),{'schema_errors':errors(putwall),'qualification':'Single-field synthetic type probe against a documented number-or-null output, not a captured quote.'})
unknown=copy.deepcopy(capture);unknown['status']='not-a-producer-status'
record('unknown-status-rejected',bool(errors(unknown)),{'rejected':bool(errors(unknown)),'qualification':'Schema status is unrestricted string; consumers must separately gate exact ok status.'})
build=datetime.fromisoformat(capture['updated_at']);wing=datetime.fromisoformat(capture['sources']['nasdaq']['as_of'])
record('build-clock-can-serve-as-complete-content-first-known',build>=wing,{'updated_at':capture['updated_at'],'nasdaq_as_of':capture['sources']['nasdaq']['as_of'],'nasdaq_after_build_seconds':(wing-build).total_seconds(),'source_build_assignment_line':selected['build_snapshot'].lineno+1,'qualification':'Pinned source assigns now before fetches; Nasdaq as_of is assigned on cache acquisition. README first-known/receipt wording cannot substitute for complete consumer receipt.'})
record('missing-raw-failure-capture-declared',any(c.get('file') is None and 'failed' in c.get('state','') for c in manifest['captures']),{'raw_failure_capture':'UNAVAILABLE as explicitly declared; offline replay is not promoted to historical capture'})
receipt={'packet_commit':'6c8eabbee034699b8c58cfb9e697c9460cf47edf','source_sha256':sha(source),'schema_sha256':sha(schemafile),'helper_sha256':sha(Path(__file__)),'jsonschema_version':importlib.metadata.version('jsonschema'),'mode':'Pinned artifact checks plus selected exact-source early/error branches; original producer module never imported; provider fetch replaced and sleep stops after one poll iteration. No server, background thread, live database or provider access.','native_provider_calls':0,'in_memory_fetch_calls':len(stub_calls),'C07':'unchanged CLOSED at29817f05; not re-tested','schema_contract_ready':False,'passed':sum(x['pass'] for x in observations),'total':len(observations),'observations':observations}
out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));sys.exit(0 if all(x['pass'] for x in observations) else 1)
