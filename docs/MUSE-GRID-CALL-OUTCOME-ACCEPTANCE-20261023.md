# Muse task — critique GRID's original-call → outcome → scoring acceptance contract

**Task ID: MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023. Status: ACK/response RECEIVED; Amendment1 at406c67a9 incorporates controller Q1/Q2. Independent review requests one bounded docs revision R1.** One bounded independent product/acceptance review, requested by MAIN. No implementation assignment. This is complementary to Codex's exact-source review of GRID PR903/904, not a duplicate code review.

## Current acceptance — completed bounded task

[Responsee6c8edb8](https://github.com/3pacs/muse/blob/e6c8edb8925afdf9ece367c19cc116162bfdcfe6/docs/MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023-RESPONSE.md), [independent acceptance](MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023-REVIEW.md) and [receipt](muse-grid-acceptance-review-0833098b/acceptance-e6c8edb8.json): all15 records strictly align to18 headers; all expected states are valid; Case8 maturity and unchanged-weight reason are separate. Existing cloud checker groups6/6, declared clocks pass for all15, and exact preservation plus grace/Case9 count checks pass. No new fixtures or broad review.

Both the numeric-policy contradiction and R1-B CSV/state corrections are VERIFIED/CLOSED. Q1/Q2 remain incorporated; production B1/B2/B3 stay unconfigured gates, not adopted fixture defaults. No more Muse revision is requested for this contract task. GRID implementation/production acceptance remains with its existing owner and is not implied by this docs closure.

Native wrapper/application/UI execution remains UNRUN; only cloud text/CSV checks were performed. No local runtime operation or host switch. Current task/PR summary is authoritative over the historical large index's old dispatch status. Original dispatch/history below is preserved.

## Owner, route and duplicate check

Owner is **Muse**, through Anik's existing primary Muse conversation and this PR2/folder workflow, as [Muse's route ACK6303374031](https://github.com/3pacs/muse/pull/2#issuecomment-6303374031) explicitly established. Return the task ID in your ACK/response through the same route. No new scheduler, runtime handle or unrelated recipient is introduced.

At dispatch preparation, PR2 head is **3513bfda2ae1a1905776fdb03fc89460bb33632c**, with76 comments, latest6354225107. Its current handoff closes Amendment2 and the prior GEX integration findings; no new substantive response or visible active Muse assignment for this GRID contract was found. This is repository-surface evidence, not proof of global idleness: **if already working this exact acceptance task, return that work's link rather than starting another; if busy with a different retained task, ACK that scope and do not create parallel implementation.** The old source/serving findings and completed MAIN decision stay closed/qualified as recorded.

## Bounded request

Independently critique what a user must see to distinguish **the original timestamped thesis**, **evidence available then**, **declared horizon/invalidation**, **what happened later**, and **how/when it was scored**. Supply a concise actionable acceptance contract and deterministic synthetic examples. Prioritize misleading presentation risks and falsifiable acceptance criteria, not styling, forecasts or model selection.

The candidate display has three linked views: **original call / observed outcome / scoring explanation**. Critique/refine that candidate; do not assume any current endpoint/UI already implements it. The immutable call must remain inspectable after new outcomes, corrections and learned weights arrive.

For every view, specify the minimal visible fields and safe unavailable/pending behavior. Cover:

1. **Original call:** stable call ID, original text/direction/target, issue and first-known times, evidence/source IDs and their observation/availability times, horizon and its calendar/timezone, explicit invalidation rule or honest “not declared,” prediction/model and learned-weight version used then. Later evidence is not “known then.” A post-hoc explanation cannot replace the original thesis.
2. **Outcome maturity:** evaluation time versus the declared horizon, price/source publication grace policy, pending window versus pending data versus matured-but-unavailable, observed invalidation versus unknown invalidation coverage. Missing/late/future/stale observations are not zeros, flat returns or losses. Do not silently close an open window as a permanent failure.
3. **Benchmark/scoring:** exact asset and benchmark identity, price/return convention, endpoint dates, comparable horizon, rule/threshold/version and eligibility reason. An index close must not be labelled an ETF fill. Show raw and benchmark-relative outcome separately where applicable; outcome agreement is not proof of profitable trading or causal value.
4. **Sample size/learning:** issued, matured, eligible/scored, pending, missing/conflicting and revised counts; score denominator, observation window and uncertainty. With n=0 display unavailable, not0%/100%; a small sample is not model superiority. Keep the original prediction's weights separate from current learned weights and the data/version used to learn them.
5. **Contradictions/corrections:** expose unresolved source conflicts and stale ages; declare a source/vintage policy before scoring. Preserve original-call and original outcome records. Later corrected-data views must state what changed, when it became known, and their separate evaluation/version; no silent historical rewrite or claim that revised weights made the original call.

## Screened synthetic fixture seeds — no market/provider lookup

These are invented assets, dates and prices, not market data or trading advice. Use a fixed synthetic calendar **CAL_SYN_1** with sessions2026-01-05,06,07,08 and close21:00Z; do not infer real exchange holidays. Reference call **C1** is issued2026-01-05T21:01Z, target ASSET_X, baseline100 observed21:00Z/known21:00:30Z, horizon2026-01-07T21:00Z, invalidation “an admitted observation at or below98 during the window.” Benchmark BENCH_Y baseline200 with matching observation/knowledge clocks. For the arithmetic control only, horizon endpoints102/202 imply raw+2%, benchmark+1%, excess+1 percentage point. Rule/version, grace policy and invalidation coverage must be explicit; this is not an assumed production scoring rule.

Use independent variants, not a changing live timeline:

| Case | Deterministic seed / ambiguity to resolve |
| --- | --- |
| Open window | Evaluate2026-01-06T21:01Z; horizon not reached. A provisional gain must not become a matured win or enter matured accuracy |
| Matured arithmetic control | Evaluate2026-01-07T21:20Z; endpoints102/202 known21:00:30Z; no source conflict. State exactly which rule is tested and what invalidation coverage remains unknown |
| Missing endpoint / publication lag | Endpoint absent at21:01Z and still absent at21:20Z. Declare a fixed10-minute grace for this synthetic case; distinguish awaiting publication from matured unavailable, without inventing a price or loss |
| Contradictory sources | ProvidersA/B report horizon102/98, both current and equally available; no source-resolution policy supplied. Do not cherry-pick the favorable result |
| Stale observation | A price102 is fetched Jan7 but its actual observation is Jan6 close. It cannot masquerade as the Jan7 endpoint |
| Known invalidation | Admitted Jan6 close97, then horizon102. Show original invalidation rule and observed breach; distinguish invalidation from terminal-return agreement instead of silently choosing whichever produces a win |
| Corrected data | Initial horizon102, initially evaluated Jan7; correction99 first known Jan8T12:00Z. Preserve initial evidence/call/evaluation, expose the correction and version, and state how any revised score is kept separate |
| Learned-weight change | C1 usedweights W1; current display usesW2 learned Jan8. Show both roles and prevent W2 being attributed to C1 or future labels entering its original evidence |
| Zero/partial sample | Cohort includes an open-window call, a missing-data call and one matured eligible control. Show each denominator/count and unavailable statistics honestly; unresolved source/invalidation coverage must be stated |

For each seed, supply fixed input clocks/IDs, expected user-visible status/labels, score eligibility, what is displayed versus withheld, and one deterministic failing presentation example. If a seed lacks a necessary policy, name the missing policy and give a labelled synthetic assumption for the test; do not claim the product already has it. Keep benchmark and correction provenance explicit.

## Deliverable and boundary

Return **one concise actionable response**: (a) minimum visible acceptance contract, (b) up to8 prioritized misleading-presentation risks with a concrete remedy, (c) the9-row deterministic acceptance matrix above, and (d) the next bounded product clarification, if any. A small JSON/CSV fixture table is welcome; executable application code is unnecessary. Link a pinned docs response in this folder/PR2, e.g. `docs/MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023-RESPONSE.md`, and identify task/source assumptions. Do not start another handoff/PR or rewrite this task's immutable dispatch context.

Context only: [GRID PR903](https://github.com/3pacs/GRID/pull/903), metadata head **594bd73fb51ab5fa0958e44bacb174a6b0a44f23**, and [PR904](https://github.com/3pacs/GRID/pull/904), metadata head **07f1245bc1ad43eb95b7419015883a84bb71e5a6**, address outcome-closing/window/benchmark concerns. **Codex owns their exact-source review.** Those heads/descriptions are dispatch context, not claims their implementation is correct, deployed or current when you respond. Do not audit either PR or read production data to fulfil this task.

**Screened scope:** docs/contract critique and invented deterministic fixtures only. No application edits, outcome backfill/rescoring, learned-weight update, production scoring, live/provider/network data acquisition, inference deployment, credential operation, schedule/automation, trading recommendation, model-superiority claim, GEX changes, or broad repository audit. Preserve PIT correctness, immutable decisions and existing ownership. Muse's own response through the existing conversation is requested; do not initiate additional GRID/external paid-provider or inference jobs, or change GRID_ALLOW_PAID_LLM. No need to inspect private data or run GRID/GEX to respond.

Muse may ACK and return the critique in one response; no extra approval step is requested. Repository publication/readback establishes delivery, not that Muse is running or has completed it.
