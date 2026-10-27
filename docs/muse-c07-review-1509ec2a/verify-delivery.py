"""Read-only artifact verification; does not execute producer/application/provider code.
Usage: python3 verify-delivery.py CURRENT_ARCHIVE_ROOT PRIOR_6D_ARCHIVE_ROOT OUTPUT_JSON
"""
from pathlib import Path
import hashlib,json,sys
root,prior,out=map(Path,sys.argv[1:])
impl=root/'implementation';base=impl/'dashboard-streaming';old=prior/'implementation/dashboard-streaming'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def match(p,e):return p.is_file() and digest(p)==e['sha256'] and ('bytes' not in e or len(p.read_bytes())==e['bytes'])
checks=[]
for line in (impl/'SHA256SUMS.txt').read_text().splitlines():
    if line.strip():
        h,p=line.split(maxsplit=1);p=p.lstrip('*');checks.append({'path':p,'match':digest(impl/p)==h})
files=['server/src/actions.ts','client/src/App.tsx','server/src/schema.ts','drizzle/0002_snapshots_table.sql','drizzle/0003_snapshot_instant.sql']
same={p:digest(base/p)==digest(old/p) for p in files}
owner=json.loads((base/'offline/snapshot-audit-c07-receipt.json').read_text())
bindings=[{'path':p,'match':digest(base/p)==h} for p,h in owner['fileHashes'].items()]
build=json.loads((base/'preview/BUILD-MANIFEST.json').read_text())
buildinputs=[{'path':e['path'],'match':match(base/e['path'],e)} for e in build['inputs']]
buildoutputs=[]
for e in build['outputs']:
    p=base/'preview'/e['path'].removeprefix('preview/')
    buildoutputs.append({'path':e['path'],'status':'MATCH' if match(p,e) else 'FAIL' if p.exists() else 'UNAVAILABLE'})
browser=base/'browser-preview';bm=json.loads((browser/'BROWSER-MANIFEST.json').read_text())
bi=[{'path':e['path'],'match':match(base/e['path'],e)} for e in bm['inputs']]
bf=[{'path':e['path'],'match':match(impl/'fixtures'/e['path'],e)} for e in bm['fixturesUsed']]
bo=[]
for e in bm['outputs']:
    p=browser/e['path'];bo.append({'path':e['path'],'status':'MATCH' if match(p,e) else 'FAIL' if p.exists() else 'UNAVAILABLE'})
by_path={e['path']:e for e in bm['outputs']}
refs=[v for c in bm['cases'] for v in c['viewports']]+bm['extraCaptures']
br=[]
for e in refs:
    output=by_path.get(e['screenshot']);p=browser/e['screenshot']
    br.append({'path':e['screenshot'],'match':p.is_file() and digest(p)==e['screenshotSha256'] and len(p.read_bytes())==e['screenshotBytes'] and output is not None and output['sha256']==e['screenshotSha256'] and output['bytes']==e['screenshotBytes']})
payload=json.loads((base/'preview/earlier-usable.payload.json').read_text())['getLive'];html=(base/'preview/earlier-usable.html').read_text()
ssr={'feed_down':payload['ok'] is False and payload['live'] is None and 'Feed status: FEED DOWN' in html,'coherent_older_frame':payload['staleSnapshotAt']==payload['staleSnapshot']['updatedAt']=='2026-01-04T23:04:00+00:00' and payload['staleSnapshot']['spot']==499.5,'earlier_note':payload['staleSnapshotReason']=='earlier-usable' and 'Showing an earlier usable saved frame.' in html,'no_live_claim':'Nothing below is live.' in html,'synthetic_labeled':'NOT MARKET DATA' in html}
asserted={'interpreter.py':'b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e','indicator_tracker.py':'8f50ab4a681c6c81cad5fe80c81c32a2474837a0396773fbe1ec8d54fa09d2f2','tape_db.py':'9031b67d59b7e05c88a43f0bcc3b590b0925bb91e27278c3bbd01ecbe4e21036','maxpain_log.py':'0b34acc40b3c520f6d40e14604417ccc00ee17e50e77998318bed3d04c5ef834'}
ack=[{'path':'implementation/pipeline/'+p,'asserted_live_sha256':h,'supplied_sha256':digest(impl/'pipeline'/p),'match':digest(impl/'pipeline'/p)==h} for p,h in asserted.items()]
bad=lambda items:[x for x in items if not x['match']]
unavailable=lambda items:[x['path'] for x in items if x['status']=='UNAVAILABLE']
fail=lambda items:[x for x in items if x['status']=='FAIL']
result={'source_commit':'1509ec2a98bd71d20b83c330c8752c6d570b010d','prior_review_source':'6d543a060ef45432dab3bb03085f86b863a0394b','scope':'New evidence/hash/reference verification only. No repeated source tests, browser execution, provider calls or runtime verification.','source_byte_identical':same,'package':{'files':sum(p.is_file() for p in impl.rglob('*')),'checksums':len(checks),'failures':bad(checks)},'owner_receipt':{'reported_summary':owner['summary'],'hash_bindings':bindings,'execution':'OWNER-RUN only; not re-executed locally'},'ssr_manifest':{'inputs':len(buildinputs),'input_failures':bad(buildinputs),'outputs':len(buildoutputs),'matched':sum(x['status']=='MATCH' for x in buildoutputs),'failures':fail(buildoutputs),'unavailable':unavailable(buildoutputs)},'ssr_payload_and_html':ssr,'browser_manifest':{'inputs':len(bi),'input_failures':bad(bi),'fixtures':len(bf),'fixture_failures':bad(bf),'available_outputs':sum(x['status']=='MATCH' for x in bo),'failures':fail(bo),'unavailable':unavailable(bo),'screenshot_references':len(br),'reference_failures':bad(br)},'MAIN_ACK_source_bindings':ack,'ACK_limit':'Live interpreter source b95d... and complete machine-readable healthy/down captures/schema are not supplied by the ACK comment. Three matching helper files corroborate their source identity only; live deployment and prose session facts remain owner assertions.','prior_result_carried_forward':{'pass':13,'total':14,'open':'returned raw updated_at disagrees with canonical key/payload clock; owner acknowledges follow-up required'},'native_provider_calls':0,'full_local_owner_stack':'UNRUN'}
passed=all(same.values()) and not bad(checks) and not bad(bindings) and not bad(buildinputs) and not fail(buildoutputs) and not bad(bi) and not bad(bf) and not fail(bo) and not bad(br) and all(ssr.values())
result['artifact_integrity_pass']=passed;result['C07_closed']=False;result['helper_sha256']=digest(Path(__file__))
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));sys.exit(0 if passed else 1)
