"""Offline review of newly supplied ported source. No deployment or live provider access.
Usage: python3 prove-port.py LOCAL_GEX_CHECKOUT REV2_SCHEMA OUTPUT_DIR
Writes a labeled fixture-driven snapshot for the separate published-normalizer check.
"""
import ast,copy,hashlib,importlib.util,json,socket,sqlite3,sys,threading,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
from jsonschema import Draft202012Validator
repo,schemafile,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
base=repo/'stopgap-20261022-muse';source=base/'out/pipeline/interpreter.py';chainfile=base/'out/gex-watch/cboe_chain.py';fixture=base/'tests/fixture-cboe-spy-trimmed.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)=='683653f97dda7ce1f264a464a9958505b7fcaebf53f665c240703c407e2dc6c1'
assert sha(schemafile)=='eac803a2562efb74fb1126ee8ef02c2492fce2c537ec09d3e9ada6839f3e44a0'
sys.dont_write_bytecode=True
blocked=[]
def deny(*args,**kwargs):blocked.append('native I/O or background operation');raise AssertionError('OFFLINE_ONLY')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
urllib.request.urlopen=deny;sqlite3.connect=deny;threading.Thread.start=deny
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
chainmod=load('offline_cboe',chainfile);interp=load('offline_ported_interpreter',source)
mapped=chainmod.map_payload(json.loads(fixture.read_text()))
now=datetime.fromisoformat(mapped['as_of'])+timedelta(seconds=3)
class FrozenDateTime(datetime):
    @classmethod
    def now(cls,tz=None):return now.astimezone(tz) if tz else now.replace(tzinfo=None)
interp.datetime=FrozenDateTime
price=mapped['current_price'];assert isinstance(price,(int,float)) and price>0
frame={'schema':'gex-screen/2','symbol':'SPY','brokerage_quote':{'status':'receipt-only','price':price,'callback_received_at':now.timestamp()-1,'receipt_time':now.timestamp()},'public_price':{'values_available':True,'price':price-1,'source_time':now.timestamp()-30}}
checks=[]
def record(name,passed,actual):checks.append({'name':name,'pass':bool(passed),'actual':actual})
q,prov=interp.legacy_quote(frame)
record('rtd-quote-collector-receipt-label',q['price']==price and prov.get('source')=='rtd' and prov.get('clock')=='collector-receipt',{'source':prov.get('source'),'clock':prov.get('clock'),'delay':prov.get('delay')})
public=copy.deepcopy(frame);public['brokerage_quote']['status']='unavailable';q,prov=interp.legacy_quote(public)
record('public-fallback-never-realtime',q['price']==price-1 and prov.get('source')=='public_price' and prov.get('delay')=='latency-unverified',{'source':prov.get('source'),'clock':prov.get('clock'),'delay':prov.get('delay')})
public['public_price']['values_available']=False;q,prov=interp.legacy_quote(public)
record('no-available-quote-stays-unavailable',q=={'price':0,'as_of':None} and prov.get('source') is None,{'quote':q,'provenance':prov})

# Small fixture-derived chain subset isolates source/provenance/schema behavior;
# it is not a production capture or held-out numerical/model evaluation.
today=now.date().isoformat();current=[x for x in mapped['contracts'] if x['expiry']==today]
strikes=sorted({x['strike'] for x in current},key=lambda k:abs(k-price))[:2]
contracts={**mapped,'contracts':[x for x in current if x['strike'] in strikes]}
calls=[]
def fetch_stub(url,timeout=12):
    calls.append(url)
    if url==interp.STATE_URL:return copy.deepcopy(frame)
    if url==interp.CONTRACTS_URL:return copy.deepcopy(contracts)
    raise AssertionError('unexpected source call')
interp.fetch_json=fetch_stub;interp.fetch_nasdaq_0dte=lambda t:[]
snapshot=interp.build_snapshot()
assert snapshot['status']=='ok'
record('delayed-chain-not-realtime',snapshot['n_strikes_rtd_live']==0 and snapshot['sources']['cboe_delayed']['delay']=='~15min' and snapshot['sources']['quote']['clock']=='collector-receipt',{'provider':'cboe_delayed','delay':snapshot['sources']['cboe_delayed']['delay'],'rtd_strikes':snapshot['n_strikes_rtd_live'],'nasdaq_strikes':snapshot['n_strikes_nasdaq_delayed'],'quote_clock':snapshot['sources']['quote']['clock']})
schema=json.loads(schemafile.read_text());v=Draft202012Validator(schema)
errs=[{'path':list(e.path),'message':e.message} for e in Draft202012Validator(schema['$defs']['ok']).iter_errors(snapshot)]
record('ported-output-admitted-by-current-rev2-schema',v.is_valid(snapshot),{'ok_variant_errors':errs,'sources':snapshot['sources'],'qualification':'Generated from controlled in-memory quote plus small retained Cboe fixture subset; not a live/captured feed response.'})
tree=ast.parse(source.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
server=next(n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ThreadingHTTPServer')
host=ast.literal_eval(server.args[0].elts[0])
record('ported-source-loopback-bind',host=='127.0.0.1',{'host':host,'qualification':'Static exported source only; actual installed process/socket not observed.'})
record('no-native-operations',not blocked,{'blocked_attempts':len(blocked),'in_memory_feed_calls':len(calls),'native_provider_calls':0,'database_or_service_operations':0})
payload=out/'synthetic-source-snapshot.json';payload.write_text(json.dumps(snapshot,allow_nan=False)+'\n')
receipt={'local_repo_commit':'b4dfd3e7bdb306fc56949381cf5ecc7348655bac','source_sha256':sha(source),'schema_sha256':sha(schemafile),'chain_mapper_sha256':sha(chainfile),'fixture_sha256':sha(fixture),'generated_fixture_snapshot_sha256':sha(payload),'helper_sha256':sha(Path(__file__)),'mode':'Read-only supplied export; native sockets/provider/DB/thread operations denied; new quote adapter controls and one fixture-based snapshot build with two source strikes. Model values are not validation or recommendations. No old C07 suite re-run.','native_provider_calls':0,'runtime_or_route_verification':'UNRUN; prose server receipt remains owner assertion','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks}
(out/'ported-source-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));sys.exit(0 if all(x['pass'] for x in checks) else 1)
