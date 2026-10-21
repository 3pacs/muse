"""Offline rev2 schema/status/clock review. No producer module import or native I/O.
Usage: python3 prove-rev2.py PACKET_ARCHIVE_ROOT OUTPUT_JSON
"""
import ast,copy,hashlib,importlib.metadata,json,sys,threading
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from jsonschema import Draft202012Validator
root,out=map(Path,sys.argv[1:]);out.parent.mkdir(parents=True,exist_ok=True)
old=root/'docs/muse-main-producer-20261020';base=root/'docs/muse-main-producer-20261020-rev2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=old/'interpreter.py';schemafile=base/'feed_all.schema.json'
assert sha(source)=='b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e'
assert sha(schemafile)=='eac803a2562efb74fb1126ee8ef02c2492fce2c537ec09d3e9ada6839f3e44a0'
manifest=json.loads((base/'manifest.json').read_text());schema=json.loads(schemafile.read_text());capture=json.loads((base/'envelope-ok-afterclose-20261020.json').read_text());readme=(base/'README.md').read_text()
observations=[]
def record(name,passed,actual):observations.append({'name':name,'pass':bool(passed),'actual':actual})
bindings=[{'path':p,'match':sha(base/p)==h} for p,h in manifest['files'].items()]
record('manifest-six-bindings',all(x['match'] for x in bindings),bindings)
preserved={p:(base/p).read_bytes()==(old/p).read_bytes() for p in ['envelope-ok-afterclose-20261020.json','healthy-session-record-20261020.json']}
record('retained-capture-bytes-preserved',all(preserved.values()),preserved)
try:Draft202012Validator.check_schema(schema);meta=True
except Exception:meta=False
record('declared-schema-valid',meta,{'dialect':schema['$schema']})
v=Draft202012Validator(schema);ok_validator=Draft202012Validator(schema['$defs']['ok'])
valid=lambda x:v.is_valid(x)
admit=lambda x:valid(x) and x.get('status')=='ok'
def compact_errors(x):return [{'path':list(e.path),'validator':e.validator,'message':e.message} for e in ok_validator.iter_errors(x)]
record('captured-afterclose-valid',valid(capture),{'market_open':capture['market_open'],'status':capture['status'],'qualification':'Historical after-close data, not current/live readiness.'})

# Same exact selected-source branches as the prior proof, now with rev2 schema.
text=source.read_text();tree=ast.parse(text)
functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
fixed=datetime.fromisoformat('2026-10-20T21:29:16.142252+00:00')
class FrozenDateTime(datetime):
    @classmethod
    def now(cls,tz=None):return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
class StopReplay(Exception):pass
calls=[]
def stop(_):raise StopReplay()
env={'datetime':FrozenDateTime,'timezone':timezone,'ET':ZoneInfo('America/New_York'),'PT':ZoneInfo('America/Los_Angeles'),'YEAR_SECONDS':365.25*24*3600,'STATE_URL':'offline:state','CONTRACTS_URL':'offline:contracts','LOCK':threading.Lock(),'SNAPSHOT':None,'time':SimpleNamespace(sleep=stop)}
for name in ['market_open_now','seconds_to_expiry','build_snapshot','poll_forever']:
    exec(compile(ast.get_source_segment(text,functions[name]),'PINNED_SOURCE:'+name,'exec'),env)
def timeout_fetch(url):calls.append(url);raise TimeoutError('OFFLINE_TIMEOUT')
env['fetch_json']=timeout_fetch
try:env['poll_forever'](30)
except StopReplay:pass
timeout=env['SNAPSHOT']
record('source-timeout-valid-and-withheld',valid(timeout) and not admit(timeout),{'envelope':timeout,'synthetic':True})
def noquote_fetch(url):
    calls.append(url)
    return {'quote':{'price':0}} if url=='offline:state' else {'contracts':[{'expiry':'2026-10-20','strike':770,'side':'C'}]}
env['fetch_json']=noquote_fetch;noquote=env['build_snapshot']()
record('source-noquote-valid-and-withheld',valid(noquote) and not admit(noquote),{'envelope':noquote,'synthetic':True})
def future_fetch(url):
    calls.append(url)
    return {'quote':{'price':771.2,'as_of':'2026-10-20T22:00:00+00:00'}} if url=='offline:state' else {'contracts':[]}
env['fetch_json']=future_fetch;future=env['build_snapshot']()
record('source-quarantine-valid-and-withheld',valid(future) and not admit(future),{'envelope':future,'synthetic':True})
starting=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SNAPSHOT' for t in n.targets))
record('source-starting-valid-and-withheld',valid(starting) and not admit(starting),{'envelope':starting,'synthetic':True})
for label,value in [('numeric',768.0),('null',None)]:
    c=copy.deepcopy(capture)
    for k in ['call_wall','put_wall','gamma_flip','max_pain']:c['gamma'][k]=value
    record('walls-'+label,valid(c),{'value':value,'synthetic':True})
c=copy.deepcopy(capture);c['status']='unknown-status';record('unknown-status-rejected',not valid(c),{'status':c['status']})
c=copy.deepcopy(capture);c.update(status='error',error='OFFLINE_TIMEOUT');record('populated-error-withheld',valid(c) and not admit(c),{'schema_valid':valid(c),'admitted':admit(c)})
record('clock-declaration-corrected','**Producer build-start time**' in readme and '**Consumer-owned**' in readme and 'before its fetches' in readme,{'qualification':'Corrected documentation inspected; no new runtime clock measurement.'})

# Execute only the exact provenance expressions, not the numerical model.
# Embed their results in otherwise retained captured data to isolate schema
# coverage. These are synthetic contract probes, not whole-source/market outputs.
nq=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_NQ' for t in n.targets))
nqenv={'_NQ':nq};exec(compile(ast.get_source_segment(text,functions['nasdaq_provenance']),'PINNED_SOURCE:nasdaq_provenance','exec'),nqenv)
empty_nasdaq=nqenv['nasdaq_provenance']()
assignments={n.targets[0].id:n for n in functions['build_snapshot'].body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
def sources(provider,asof,nasdaq):
    e={'chain_provider':provider,'chain_as_of':asof,'chain_delay':'realtime' if provider=='rtd' else 'delayed','chain_strikes':3,'nq_prov':nasdaq,'n_nasdaq':0 if nasdaq['as_of'] is None else 143}
    e['chain_src']=eval(compile(ast.Expression(assignments['chain_src'].value),'PINNED_SOURCE:chain_src','eval'),e)
    return eval(compile(ast.Expression(assignments['sources'].value),'PINNED_SOURCE:sources','eval'),e)
c=copy.deepcopy(capture);c['sources']=sources('rtd',capture['quote_as_of'],empty_nasdaq);c['n_strikes_nasdaq_delayed']=0
record('source-null-nasdaq-clock-admitted',valid(c),{'sources':c['sources'],'ok_variant_errors':compact_errors(c),'synthetic':'Exact source provenance expressions with initial empty Nasdaq cache, embedded in retained envelope for schema isolation.'})
c=copy.deepcopy(capture);c['quote_as_of']=None;c['sources']=sources('rtd',None,capture['sources']['nasdaq'])
record('source-null-rtd-clock-admitted',valid(c),{'quote_as_of':None,'sources':c['sources'],'ok_variant_errors':compact_errors(c),'synthetic':'Exact source provenance expressions with absent quote/chain clocks; no timestamp invented.'})
c=copy.deepcopy(capture);c['sources']=sources('vendor_delayed',capture['quote_as_of'],capture['sources']['nasdaq']);c['n_strikes_rtd_live']=0
record('source-declared-alternate-provider-admitted',valid(c),{'sources':c['sources'],'ok_variant_errors':compact_errors(c),'synthetic':'Exact source dynamic chain-provider key; contract can instead explicitly declare this source branch unsupported.'})
receipt={'packet_commit':'161db1ede6cdfaf759181027dae404223d9fcf51','source_sha256':sha(source),'schema_sha256':sha(schemafile),'helper_sha256':sha(Path(__file__)),'jsonschema_version':importlib.metadata.version('jsonschema'),'mode':'Artifact/schema checks; selected exact-source early/error and provenance expressions only. No producer module import, numerical model, native fetch, database, server or thread startup.','native_provider_calls':0,'in_memory_fetch_calls':len(calls),'C07':'unchanged CLOSED at29817f05; not re-tested','passed':sum(x['pass'] for x in observations),'total':len(observations),'observations':observations}
out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':receipt['passed'],'total':receipt['total'],'helper_sha256':receipt['helper_sha256'],'failed':[x for x in observations if not x['pass']]},indent=2));sys.exit(0 if all(x['pass'] for x in observations) else 1)
