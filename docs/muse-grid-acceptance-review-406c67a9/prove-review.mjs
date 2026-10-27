#!/usr/bin/env node
// Offline review of exact Muse response 406c67a9. Run: node prove-review.mjs RESPONSE.md
// Checks documentation consistency and fixture arithmetic, not GRID application behavior.
import fs from 'node:fs';
import crypto from 'node:crypto';
const sourceBytes = fs.readFileSync(process.argv[2]);
const blob = crypto.createHash('sha1').update(Buffer.from('blob '+sourceBytes.length+'\0')).update(sourceBytes).digest('hex');
if (blob !== 'f1009ebc53edd45e37579890f4bbdf5a7c2c2e66') throw new Error('Wrong response blob; review new source separately');
const reviewChecks = function reviewChecks(source) {
  const checks=[];
  const rec=(name,pass,detail)=>checks.push({name,pass:!!pass,detail});
  const near=(a,b)=>Math.abs(a-b)<1e-9;
  const raw=100*(102/100-1),benchmark=100*(202/200-1);
  rec("control-return-arithmetic",near(raw,2)&&near(benchmark,1)&&near(raw-benchmark,1),{raw_percent:raw,benchmark_percent:benchmark,excess_percentage_points:raw-benchmark});
  const corrected=100*(99/100-1);
  rec("corrected-vintage-arithmetic",near(corrected,-1)&&near(corrected-benchmark,-2),{raw_percent:corrected,excess_percentage_points:corrected-benchmark});
  rec("pending-and-grace-clock-controls",Date.parse("2026-01-06T21:01:00Z")<Date.parse("2026-01-07T21:00:00Z")&&Date.parse("2026-01-07T21:01:00Z")<Date.parse("2026-01-07T21:10:00Z")&&Date.parse("2026-01-07T21:20:00Z")>Date.parse("2026-01-07T21:10:00Z"),{window_eval:"2026-01-06T21:01:00Z",horizon:"2026-01-07T21:00:00Z",grace_end:"2026-01-07T21:10:00Z"});
  const blanket=source.includes("no numeric return is rendered anywhere");
  const preHorizonReturn=source.includes("provisional mark +1.0%");
  const unresolvedCandidates=source.includes("both candidate returns, each tagged with its provider");
  const assertion2=source.includes("No surface ever renders a numeric return for a call lacking an admitted horizon endpoint (Cases 3, 4, 5)");
  rec("numeric-return-policy-is-internally-consistent",!(blanket&&(preHorizonReturn||unresolvedCandidates))&&!(assertion2&&unresolvedCandidates),{blanket_no_return:blanket,provisional_return_display:preHorizonReturn,conflict_candidate_returns_display:unresolvedCandidates,assertion2_forbids_case4:assertion2});
  const case7=source.split("### Case 7 — Corrected data")[1]?.split("### Case 8")[0]||"";
  const case8=source.split("### Case 8 — Learned-weight change")[1]?.split("### Case 9")[0]||"";
  const case9=source.split("### Case 9 — Zero / partial sample")[1]?.split("## (d)")[0]||"";
  const incomplete={
    E2_evaluated_at_not_fixed:case7.includes("New evaluation `E2`")&&!/E2`?\s+(?:evaluated_at|evaluated-at|evaluated|at)\s*[:=]?\s*2026-\d\d-\d\dT\d\d:\d\dZ/.test(case7),
    case8_evaluation_is_only_after_date:source.includes("| 8 Learned-weight change | after 2026-01-08")&&case8.includes("On 2026-01-08, weights `W2`"),
    case9_evaluation_is_after_not_at:case9.includes("eval after 2026-01-07T21:20Z"),
    case9_C2_horizon_not_fixed:case9.includes("`C2` = a call still inside its window")&&!/C2.{0,100}horizon[^.\n]*2026-\d\d-\d\dT\d\d:\d\dZ/.test(case9)
  };
  rec("cases7-to9-have-complete-fixed-evaluation-inputs",!Object.values(incomplete).some(Boolean),incomplete);
  return {mode:"Cloud-only arithmetic and exact-source text consistency checks; no application/runtime execution",passed:checks.filter(c=>c.pass).length,total:checks.length,checks};
};
const source=sourceBytes.toString('utf8');
const result = reviewChecks(source);
const q1 = source.includes("| 3.5 | Two-leg headline:") && source.includes("`INVALIDATION: BREACHED` + `RETURN: CORRECT (+2.00% / +1.00pp)`") && source.includes("13. No surface renders a single collapsed win/loss headline");
const q2 = source.includes("**Q2 — Production policy values: RESOLVED as unconfigured.**") && ["| B1 |","| B2 |","| B3 |"].every(s => source.includes(s)) && source.includes("14. On any production surface where gate B1, B2, or B3 is unbound");
result.checks.push({name:"amendment-two-explicit-headline-legs",pass:q1},{name:"amendment-unconfigured-production-bindings-withheld",pass:q2});
result.passed=result.checks.filter(c=>c.pass).length; result.total=result.checks.length;

result.mode = 'Offline exact-source documentation/arithmetic checks; no GRID application/runtime execution';
console.log(JSON.stringify({source_commit:'406c67a9aa6f378e90d5d09a32b3b3c5c290a5a5',source_blob:blob,...result},null,2));
process.exitCode = result.passed === result.total ? 0 : 1;
