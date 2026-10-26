#!/usr/bin/env node
// Offline checks for pinned Muse synthetic fixture CSV; no network or GRID imports.
// node prove-fixture.mjs RESPONSE.md ; expected exit1 at0833098b (4/6 groups).
import fs from 'node:fs';
import crypto from 'node:crypto';
const bytes=fs.readFileSync(process.argv[2]);
const blob=crypto.createHash('sha1').update(Buffer.from('blob '+bytes.length+'\0')).update(bytes).digest('hex');
if(blob!=='b9cefea7e7b790f86969bf531f719ce7f8bd6026')throw Error('Unexpected source blob; review new revisions separately');
const assessR1=function assessR1(source){
 function csv(text){let rows=[],row=[],field="",q=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(q&&text[i+1]==='"'){field+='"';i++;}else q=!q;}else if(c===','&&!q){row.push(field);field="";}else if(c==='\n'&&!q){row.push(field);rows.push(row);row=[];field="";}else if(c!=='\r')field+=c;}if(q)throw Error("unclosed CSV quote");if(field.length||row.length){row.push(field);rows.push(row);}return rows;}
 const block=source.match(/```csv\n([\s\S]*?)\n```/)?.[1];if(!block)throw Error("CSV block absent");
 const rows=csv(block),header=rows.shift(),valid=[],badWidths=[];
 for(const row of rows){if(row.length!==header.length){badWidths.push({case:row[0],actual_fields:row.length,expected_fields:header.length});continue;}valid.push(Object.fromEntries(header.map((h,i)=>[h,row[i]])));}
 const allowed=["OPEN","PENDING-PUBLICATION","MATURED","MATURED-UNAVAILABLE","CONFLICT","STALE-ONLY"];
 const badStates=valid.filter(r=>!allowed.includes(r.expected_state)).map(r=>({case:r.case,actual_state:r.expected_state,allowed}));
 const timeBad=valid.filter(r=>![r.issued_at,r.baseline_obs,r.baseline_known,r.horizon_at,r.eval_at].every(x=>Number.isFinite(Date.parse(x)))||Date.parse(r.baseline_obs)>Date.parse(r.baseline_known)||Date.parse(r.baseline_known)>Date.parse(r.issued_at)||(r.endpoint_known&&(!Number.isFinite(Date.parse(r.endpoint_known))||Date.parse(r.endpoint_known)>Date.parse(r.eval_at)))).map(r=>r.case);
 const checks=[
 {name:"NUM-CLASS-1-aligns-provisional-candidate-and-scored-rules",pass:source.includes("**Numeric-return invariant `NUM-CLASS-1`")&&source.includes("Class B/C arithmetic, where it exists")&&!source.includes("no numeric return is rendered anywhere"),detail:"Original numeric-blanket finding closed at document level; classes remain labelled/unscored as declared."},
 {name:"fixture-header-has-18-unique-fields",pass:header.length===18&&new Set(header).size===header.length,detail:{fields:header.length}},
 {name:"all-fixture-records-align-with-header",pass:badWidths.length===0,detail:badWidths},
 {name:"well-shaped-records-use-contract-state-enum",pass:badStates.length===0,detail:badStates},
 {name:"well-shaped-records-preserve-declared-knowledge-clocks",pass:timeBad.length===0,detail:{validated_rows:valid.length,rejected_for_width:badWidths.length,invalid_clock_cases:timeBad,limitation:"Malformed records are rejected, never truncated or silently repaired."}},
 {name:"controller-two-legs-and-unconfigured-policy-gates-preserved",pass:source.includes("| 3.5 | Two-leg headline:")&&source.includes("**Q2 — Production policy values: RESOLVED as unconfigured.**")&&["| B1 |","| B2 |","| B3 |"].every(x=>source.includes(x)),detail:"No repeated production clarification requested."}
 ];
 return {mode:"Cloud-only exact-document CSV parsing and declared-field checks; no GRID application/native runtime execution",passed:checks.filter(c=>c.pass).length,total:checks.length,fixture_rows:rows.length,well_shaped_rows:valid.length,checks};
};
const result=assessR1(bytes.toString('utf8'));
result.mode='Offline exact-document CSV/field checks; no GRID application/native service execution';
console.log(JSON.stringify({source_commit:'0833098bccbb6bf2d0c9123a34c6af327733c715',source_blob:blob,...result},null,2));
process.exitCode=result.passed===result.total?0:1;
