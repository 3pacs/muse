"""Static source/contract reference check only. Does not execute main, server, polls or deploy.
Usage: python3 check-deployment-reference.py PACKET_ARCHIVE_ROOT OUTPUT_JSON
"""
import ast,hashlib,json,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:]);out.parent.mkdir(parents=True,exist_ok=True)
base=root/'docs';old=base/'muse-main-producer-20261020/interpreter.py';target=base/'muse-gex-deploy-20261020/interpreter.py';seal=target.parent/'SEAL-MANIFEST.sha256'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(old)=='b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e'
old_tree=ast.parse(old.read_text());target_tree=ast.parse(target.read_text())
funcs=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
a,b=funcs(old_tree),funcs(target_tree)
source_hash=sha(target);seal_hash=sha(seal)
assert source_hash=='cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0'
assert seal_hash=='7e2c3ff3903dc5a4ccf6dbbde37bd48e547d1a51abb768e8f667eddb19fbc1b7'
pure_same={n:ast.dump(a[n],include_attributes=False)==ast.dump(b[n],include_attributes=False) for n in ['market_open_now','seconds_to_expiry','nasdaq_provenance']}
def returns(node):return [ast.dump(n.value,include_attributes=False) for n in ast.walk(node) if isinstance(n,ast.Return)]
return_expressions_same=returns(a['build_snapshot'])==returns(b['build_snapshot'])
def assignment(fn,name):return next(n.value for n in fn.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id==name)
provenance_same={n:ast.dump(assignment(a['build_snapshot'],n),include_attributes=False)==ast.dump(assignment(b['build_snapshot'],n),include_attributes=False) for n in ['chain_src','sources']}
main=b['main']
server_call=next(n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ThreadingHTTPServer')
address=server_call.args[0];bind_host=ast.literal_eval(address.elts[0]);port_expression=ast.unparse(address.elts[1])
flags=[ast.literal_eval(n.args[0]) for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument' and n.args]
result={'docs_commit':'5e55099810e7de56540e54d16afcf2efc2e6cd5f','target_source_sha256':source_hash,'target_hash_matches':source_hash=='cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0','seal_manifest_sha256':seal_hash,'seal_manifest_hash_matches':seal_hash=='7e2c3ff3903dc5a4ccf6dbbde37bd48e547d1a51abb768e8f667eddb19fbc1b7','schema_declared_producer_pin':'b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e','target_is_distinct_source':source_hash!=sha(old),'contract_pure_helpers_ast_same':pure_same,'build_snapshot_return_expressions_ast_same':return_expressions_same,'provenance_expressions_ast_same':provenance_same,'source_clock_provider_coverage_findings':'The exact provenance expressions producing nullable as_of and dynamic provider keys are identical in b95d and cb4f. Rev2 coverage failures apply to those expressions; no broad equivalence or numerical/runtime acceptance is claimed.','deployment_bind_spec':'127.0.0.1 only, --port8788, only TAPE_DB source edit permitted','static_main_bind':bind_host,'port_expression':port_expression,'cli_flags':flags,'provided_invocation_meets_loopback_spec':bind_host=='127.0.0.1','bind_finding':'main hardcodes 0.0.0.0; --port changes only the port. The supplied invocation does not itself satisfy the loopback bind requirement. Resolve an explicit isolation/binding mechanism or implementation/spec pin; no runtime reachability/exposure assertion.','deployment_status':'OWNER ORDER/REFERENCE ONLY, not executed or verified. No server-agent receipt supplied.','seal_scope':'Interpreter hash matches its one row in the supplied seal; other referenced test/log artifacts are not included here. Earlier SOUND claim is not independently re-established by this static check.','native_provider_calls':0,'runtime_or_route_calls':0,'C07':'CLOSED and unchanged','helper_sha256':sha(Path(__file__))}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(0 if result['provided_invocation_meets_loopback_spec'] else 1)
