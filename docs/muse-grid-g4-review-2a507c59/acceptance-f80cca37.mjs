#!/usr/bin/env node
// Reviewer-owned successor checker. Original 2a507c59 failing proof remains unchanged.
// Native wrapper UNRUN; the assess body was executed only in cloud over fetched invented text.
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
const input=process.argv[2];
if(!input)throw new Error("Usage: node acceptance-f80cca37.mjs RESPONSE.md");
const bytes=readFileSync(input);
const blob=createHash("sha1").update(Buffer.from("blob "+bytes.length+"\0")).update(bytes).digest("hex");
if(blob!=="aa13cf3b4c83bd6ca69bc819041c0abc4f803e08")throw new Error("Wrong input blob: "+blob);
const assess=function assess(document) {
  const checks=[];
  const check=(id,pass,details)=>checks.push({id,pass:Boolean(pass),details});
  const blocks=[...document.matchAll(/```json\s*\n([\s\S]*?)```/g)];
  if(blocks.length!==1) return {checks:[{id:"json-block",pass:false,details:"Expected exactly one JSON block"}]};
  let cases;try{cases=JSON.parse(blocks[0][1]);}catch(e){return {checks:[{id:"json-parse",pass:false,details:String(e)}]};}
  const at=Object.fromEntries(cases.map(c=>[c.case_id,c]));
  const iso=s=>typeof s==="string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(s)&&Number.isFinite(Date.parse(s));
  const known=s=>s!==undefined&&s!==null&&s!=="UNKNOWN";
  const keys=v=>Object.keys(v).sort().join("|");
  const paths=["writer","hermes_refresher","manual_api","direct_flow"];
  const receipt=(c,type,scope)=>c.receipts.some(r=>r.type===type&&r.scope===scope&&iso(r.at)&&Date.parse(r.at)<=Date.parse(c.evaluated_at));
  const loaded=c=>(known(c.writer.loaded_version_or_state)||known(c.writer.hold))&&receipt(c,"WRITER_LOADED_STATE","writer");
  const zeroCoverage=c=>paths.filter(p=>receipt(c,"ZERO_IN_FLIGHT",p));
  const consumersCovered=c=>c.consumers.length>0&&c.consumers.every(x=>x.id!=="UNKNOWN"&&(receipt(c,"CONSUMER_ADOPTION",x.id)||receipt(c,"CONSUMER_EXCLUSION",x.id)));
  const barrier1=c=>loaded(c)&&zeroCoverage(c).length===paths.length&&consumersCovered(c);
  const barrier2=c=>paths.every(p=>c.renewal_paths[p]==="FENCED"&&receipt(c,"FENCE",p))&&c.registry.rows.length===0&&receipt(c,"REGISTRY_INVALIDATION",c.snapshot_id+"_V1")&&receipt(c,"CACHE_INVALIDATION","cache");
  const eligibility=c=>{const latest=new Map();for(const r of c.refreshes){if(Date.parse(r.refreshed_at)<=Date.parse(c.evaluated_at)&&(!latest.has(r.version_id)||Date.parse(r.refreshed_at)>Date.parse(latest.get(r.version_id).refreshed_at)))latest.set(r.version_id,r);}return [...latest.values()].map(r=>({version:r.version_id,eligible:r.expires_at===null?c.eligible_under_named_rule.rule==="UNSAFE-NULL-ELIGIBLE-1":Date.parse(c.evaluated_at)<Date.parse(r.expires_at)}));};
  check("G01-schema",cases.length===8&&Object.keys(at).sort().join()==="F1,F2,F3,F4,F5,F6,F7,F8"&&cases.every(c=>keys(c)===keys(cases[0])&&c.refreshes.every(r=>keys(r)==="expires_at|expires_at_before|refreshed_at|version_id")),{cases:cases.length,fields:Object.keys(cases[0]).length});
  check("G02-identities",new Set(cases.map(c=>c.snapshot_id)).size===8&&cases.every(c=>c.snapshot_id==="SNAP_"+c.case_id),{snapshotIds:cases.map(c=>c.snapshot_id)});
  check("G03-clocks",cases.every(c=>iso(c.original_observed_at)&&iso(c.first_known_at)&&iso(c.evaluated_at)&&Date.parse(c.original_observed_at)<=Date.parse(c.first_known_at)&&c.refreshes.every(r=>iso(r.refreshed_at)&&Date.parse(c.first_known_at)<=Date.parse(r.refreshed_at)&&Date.parse(r.refreshed_at)<=Date.parse(c.evaluated_at)&&(r.expires_at===null||iso(r.expires_at))&&(r.expires_at_before==="UNKNOWN"||iso(r.expires_at_before)))&&c.receipts.every(r=>iso(r.at)&&Date.parse(r.at)<=Date.parse(c.evaluated_at))),"Top-level observation/knowledge/refresh/evaluation and all explicit receipt clocks; per-version coverage is checked separately.");
  check("G04-refresh-arithmetic",cases.every(c=>c.refreshes.every(r=>r.expires_at===null||Date.parse(r.expires_at)-Date.parse(r.refreshed_at)===4*3600000)),"Every non-null expiry is exactly four synthetic hours after refresh.");
  check("G05-selector-eligibility",cases.every(c=>eligibility(c).every(e=>e.eligible===c.eligible_under_named_rule.eligible)),cases.map(c=>({case:c.case_id,computed:eligibility(c),claimed:c.eligible_under_named_rule.eligible})));
  const f1=at.F1,f8=at.F8;
  const ages={observationMinutes:(Date.parse(f1.evaluated_at)-Date.parse(f1.original_observed_at))/60000,firstRefreshMinutes:(Date.parse(f1.evaluated_at)-Date.parse(f1.refreshes[0].refreshed_at))/60000,renewedRemainingMinutes:(Date.parse(f1.refreshes[1].expires_at)-Date.parse(f1.evaluated_at))/60000};
  check("G06-F1-ages",ages.observationMinutes===1921&&ages.firstRefreshMinutes===241&&ages.renewedRemainingMinutes===238,ages);
  const withoutRenewal=JSON.parse(JSON.stringify(f1));withoutRenewal.refreshes.pop();
  check("G07-renewal-negative-control",eligibility(f1).at(-1).eligible&&!eligibility(withoutRenewal)[0].eligible,{withRenewal:true,withoutRenewal:eligibility(withoutRenewal)[0].eligible,syntheticBoundaryAtExpiry:Date.parse("2026-01-20T16:00:00Z")<Date.parse("2026-01-20T16:00:00Z")});
  check("G08-manual-and-Hermes",cases.every(c=>keys(c.renewal_paths)===paths.slice().sort().join("|"))&&at.F6.renewal_paths.manual_api==="ELIGIBLE"&&at.F6.renewal_paths.hermes_refresher==="FENCED"&&at.F7.renewal_paths.manual_api==="FENCED"&&at.F7.renewal_paths.hermes_refresher==="ELIGIBLE"&&!barrier2(at.F6)&&!barrier2(at.F7),"Both renewal paths are separately enumerated; closing one cannot satisfy the complete fence.");
  check("G09-F8-receipt-order",Math.max(...f8.receipts.map(r=>Date.parse(r.at)))===Date.parse("2026-01-20T14:53:00Z")&&f8.receipts.every(r=>Date.parse(r.at)<Date.parse(f8.refreshes[0].expires_at)),{completeAt:"2026-01-20T14:53:00Z",expiry:f8.refreshes[0].expires_at});
  check("G10-F8-consumers",consumersCovered(f8)&&f8.consumers.map(c=>c.id).join("|")==="CONSUMER_A|CONSUMER_B","Both finite named consumers have matching adoption receipts.");
  check("G11-F8-writer-loaded-state",loaded(f8),{writer:f8.writer,declaredBarrier1:f8.barrier_1_state,requiredBy:"SAFE-2BAR-1 §0.3: loaded version or state is known; renewal-path FENCE is a separate fact."});
  check("G12-F8-inflight-coverage",zeroCoverage(f8).length===paths.length,{requiredInventory:paths,receiptedZeroPaths:zeroCoverage(f8),globalClaim:f8.in_flight,unreceiptedPaths:paths.filter(p=>!zeroCoverage(f8).includes(p))});
  const strings=v=>typeof v==="string"?[v]:v&&typeof v==="object"?Object.values(v).flatMap(strings):[];
  const f5strings=strings(at.F5);
  check("G13-F5-per-version-observation",["2026-01-20T10:00:00Z","2026-01-20T10:01:00Z"].every(s=>f5strings.includes(s)),{V2Observation:"2026-01-20T10:00:00Z",V2Known:"2026-01-20T10:01:00Z",presentInMachineFixture:["2026-01-20T10:00:00Z","2026-01-20T10:01:00Z"].every(s=>f5strings.includes(s)),narrativePresent:document.includes("`V2`: observed `2026-01-20T10:00:00Z`, known `2026-01-20T10:01:00Z`")});
  const dropManual=JSON.parse(JSON.stringify(f8));dropManual.receipts=dropManual.receipts.filter(r=>!(r.type==="FENCE"&&r.scope==="manual_api"));
  const dropCache=JSON.parse(JSON.stringify(f8));dropCache.receipts=dropCache.receipts.filter(r=>r.type!=="CACHE_INVALIDATION");
  check("G14-retirement-proof-negative-controls",barrier2(f8)&&!barrier2(dropManual)&&!barrier2(dropCache)&&barrier1(f8),{materializationReceipts:barrier2(f8),withoutManualFence:barrier2(dropManual),withoutCacheInvalidation:barrier2(dropCache),recomputedAdoptionBarrier:barrier1(f8),claimedRetirement:f8.safe_contract_acceptance});
  check("G15-withholding",cases.every(c=>Array.isArray(c.withheld_claims)&&c.withheld_claims.length>0)&&document.includes("POLICY_UNCONFIGURED")&&f8.withheld_claims.includes("production retirement")&&f8.withheld_claims.includes("production inventory coverage"),"Production policy/retirement/coverage are withheld, with no production numeric policy adopted.");
  const nullPaths=[];function visit(v,path){if(v===null)nullPaths.push(path);else if(v&&typeof v==="object")for(const [k,x]of Object.entries(v))visit(x,path+"."+k);}
  cases.forEach(c=>visit(c,c.case_id));
  check("G16-null-versus-unknown",nullPaths.length===2&&nullPaths.every(p=>p.startsWith("F4.")&&p.endsWith("expires_at")||p==="F4.expires_at_at_evaluation")&&cases.filter(c=>c.case_id!=="F8").every(c=>c.in_flight==="UNKNOWN"),{nullPaths});
  check("G17-unsafe-mechanism-coverage",["UNSAFE-REFRESH-TTL-1","UNSAFE-NULL-ELIGIBLE-1","UNSAFE-HOLD-GLOBAL-1","UNSAFE-EMPTY-RETRACT-1","UNSAFE-LATEST-WINS-1"].every(id=>cases.some(c=>c.policy_rule_ids.includes(id))),"All five challenged mechanisms are named.");
  check("G18-policy-gap-list",Array.from({length:10},(_,i)=>"GAP-"+String(i+1).padStart(2,"0")).every(id=>document.includes("**"+id+" —")),"Ten named missing production bindings; no fabricated production thresholds.");
  check("G19-independent-barrier-output",cases.every(c=>known(c.barrier_1_state)&&known(c.barrier_2_state)&&known(c.failing_display?.display)&&known(c.failing_display?.falsified_by))&&cases.filter(c=>c.safe_contract_acceptance==="NOT_ACCEPTED").length===7,"Separate labels and failing examples exist in all eight; positive proof sufficiency is independently checked above.");

  const versionClocksOK=c=>Array.isArray(c.version_clocks)&&new Set(c.version_clocks.map(v=>v.version_id)).size===c.version_clocks.length&&c.version_clocks.length===new Set(c.refreshes.map(r=>r.version_id)).size&&c.refreshes.every(r=>{const v=c.version_clocks.find(v=>v.version_id===r.version_id);return v&&iso(v.original_observed_at)&&iso(v.first_known_at)&&Date.parse(v.original_observed_at)<=Date.parse(v.first_known_at)&&Date.parse(v.first_known_at)<=Date.parse(r.refreshed_at);})&&c.version_clocks[0].original_observed_at===c.original_observed_at&&c.version_clocks[0].first_known_at===c.first_known_at;
  check("G20-version-clock-bindings",cases.every(versionClocksOK)&&at.F5.version_clocks.some(v=>v.version_id==="V2"&&v.original_observed_at==="2026-01-20T10:00:00Z"&&v.first_known_at==="2026-01-20T10:01:00Z"),"Every refresh version has exactly one coherent observation/knowledge binding; top-level clocks match V1, and F5 V2 keeps its seeded clocks.");
  const dropLoaded=JSON.parse(JSON.stringify(f8));dropLoaded.receipts=dropLoaded.receipts.filter(r=>r.type!=="WRITER_LOADED_STATE");
  const dropHermesZero=JSON.parse(JSON.stringify(f8));dropHermesZero.receipts=dropHermesZero.receipts.filter(r=>!(r.type==="ZERO_IN_FLIGHT"&&r.scope==="hermes_refresher"));
  const dropV2=JSON.parse(JSON.stringify(at.F5));dropV2.version_clocks=dropV2.version_clocks.filter(v=>v.version_id!=="V2");
  check("G21-R1-negative-controls",barrier1(f8)&&!barrier1(dropLoaded)&&!barrier1(dropHermesZero)&&versionClocksOK(at.F5)&&!versionClocksOK(dropV2),{positiveAdoptionBarrier:barrier1(f8),withoutLoadedReceipt:barrier1(dropLoaded),withoutHermesZero:barrier1(dropHermesZero),withoutV2Clocks:versionClocksOK(dropV2)});
  return {groups:checks.length,passed:checks.filter(c=>c.pass).length,failed:checks.filter(c=>!c.pass).length,checks,limits:"Cloud reviewer-authored document/fixture checks only. Native execution and GRID runtime/source/production claims are UNRUN/unverified."};
};
const result=assess(bytes.toString("utf8"));
console.log(JSON.stringify({source_commit:"f80cca3787c595cc2876665fc1e15a09d281ab80",source_blob:blob,...result},null,2));
process.exitCode=result.failed?1:0;
