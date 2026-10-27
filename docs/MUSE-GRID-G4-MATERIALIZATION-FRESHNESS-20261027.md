# Muse task — G4 materialization freshness and two-barrier adoption

**Task ID: MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027. Status: DISPATCHED; Muse availability/ACK and final response NOT YET RECEIVED.**
One synthetic-only acceptance critique for Muse through the existing primary-conversation / draft PR2 / docs-folder route. This is distinct from daily intelligence and the completed R1-B original-call/outcome task. R1-B remains CLOSED at [01861af0](https://github.com/3pacs/muse/commit/01861af044a8ac7b4665c2bd0f11bbd53a3b0bbf); no replay or reopened correction.

## Ownership, pickup and evidence

Repository duplicate check before dispatch: PR2 is open/draft at 01861af044a8ac7b4665c2bd0f11bbd53a3b0bbf, 83 comments, latest Muse response6411887045; no newer comment, task file or visible same-scope assignment. Other open PR1/PR3 have only historical October4/5 updates. The historical large index's old QUEUED/in-progress text is not current availability evidence; the completed task and current PR summary supersede it. There is no verified live Muse availability endpoint. This establishes no visible collision, not global idleness or actual pickup.

Use only the established [route ACK6303374031](https://github.com/3pacs/muse/pull/2#issuecomment-6303374031), not its historical runtime description as current architecture. **Before starting, ACK this task ID, current availability and claimed synthetic/docs scope; if already busy or this exact task exists, link the active task and do not start a duplicate.** ACK may accompany the final response. Delivery, ACK and completion will be recorded separately. No new executor, provider route, scheduler or competing writer.

Existing GRID authors and exact-source reviewer retain application work; ROOT retains sole Alien release ownership. Muse is an acceptance/doc contributor only. No GRID source pin or implementation assertion is supplied or required: all rules below are hypothetical synthetic mechanisms to challenge.

## Question: two barriers must remain separately visible

Describe what evidence a user needs for:
1. **Loaded/in-flight/adoption barrier:** writer loaded version, in-flight work disposition, and separately each consumer/subscriber's adoption or exclusion proof. A compatible writer HOLD does not establish other paths are fenced.
2. **Materialization barrier:** disposition of already materialized registry rows, refreshers, direct-flow paths and caches, including explicit invalidation/retraction and evidence no eligible renewal remains.

Neither barrier proves the other. A green writer or “four hours elapsed” must not become “old materialization retired.” A refresh may set refreshed_at=now and expires_at=now+4h without checking original observation age; an empty register may leave old rows untouched; NULL expiry and overlapping versions may remain eligible. Count both an authenticated manual API path and Hermes refreshers when testing renewal reachability. Authentication is a synthetic path property, not permission to invoke it.

## Deliverable — at most eight fixed-clock cases

Return one concise response in `docs/MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027-RESPONSE.md`, with a fenced, parseable JSON fixture table (or companion JSON file), plus a short policy-gap list. At most eight independent cases; all data, identities and clocks invented. No code audit or application executable is needed.

For each case pin:
- Case/policy/snapshot/version IDs; evaluated_at; original_observed_at and first_known_at; refresh times and expiry before/after (explicit null versus UNKNOWN); original snapshot identity retained across refresh.
- Writer loaded version/HOLD, in-flight facts, consumer/subscriber inventory/adoption, registry rows/overlaps, cache disposition, and manual API/Hermes renewal path state. Use explicit known fixture facts versus UNKNOWN; an absent receipt is not a false/zero fact.
- Expected separate barrier states, user-visible labels, eligibility under the named synthetic rule, safe disposition/withheld claims and minimal retirement proof still missing.
- One concrete failing display/inference and why it is falsified by those inputs. Keep admitted-under-unsafe-rule distinct from accepted-by-a-safe-contract; do not hide that an unsafe row remains technically eligible.

Use these eight seed slots; refine their expectations without increasing the case count. Every date below is an invented UTC test clock, unrelated to current market data. Fill every unspecified fact as UNKNOWN or a clearly named synthetic assumption, never a real-world assertion.

| Case | Fixed seed and challenge |
| --- | --- |
| F1 Renewed old observation | Observe Jan19 08:00Z; first-known08:01Z; refresh Jan20 12:00Z, expiry16:00Z; refresh again15:59Z, expiry19:59Z; evaluate16:01Z. Same snapshot ID. Hypothetical refresh ignores original age. More than four hours after the first refresh is not retirement proof while renewal remains eligible. |
| F2 Writer HOLD only | Observe Jan20 10:00Z; known10:01Z; refresh12:00Z, expiry16:00Z; evaluate12:30Z. Compatible writer HOLD known; in-flight UNKNOWN; registry/direct-flow open; subscriber adoption UNKNOWN; cache contains old row. Writer HOLD cannot fence these paths by implication. |
| F3 Empty register | Observe Jan20 10:00Z; known10:01Z; refresh11:00Z, expiry15:00Z; empty registration at12:00Z; evaluate12:01Z. Synthetic register is no-op on empty input, old registry/cache retained. Empty input is not retraction. |
| F4 NULL expiry | Observe Jan19 08:00Z; known08:01Z; refresh Jan20 12:00Z; expires_at=null; evaluate16:01Z. Hypothetical selector accepts NULL expiry. Distinguish null from unknown clock; no invented automatic expiry. |
| F5 Overlapping versions | V1 observed Jan20 09:00Z/known09:01Z, refresh11:00Z/expiry15:00Z; V2 observed10:00Z/known10:01Z, refresh12:00Z/expiry16:00Z; evaluate12:30Z. Both registry versions match; subscriber has V1 cache. “V2 registered” alone does not prove V1 removal, precedence or adoption. |
| F6 Manual path omitted | Observe Jan19 08:00Z; known08:01Z; manual authenticated refresh Jan20 15:59Z/expiry19:59Z; evaluate16:01Z. Hermes fenced, manual path explicitly eligible, writer HOLD; subscriber evidence UNKNOWN. A fence inventory excluding manual API is incomplete. |
| F7 Refresher omitted | Observe Jan19 08:00Z; known08:01Z; Hermes refresh Jan20 15:59Z/expiry19:59Z; evaluate16:01Z. Manual API fenced, Hermes explicitly eligible, writer HOLD; subscriber evidence UNKNOWN. Manual-route closure is not a complete renewal fence. |
| F8 Positive proof / boundary control | Observe Jan20 10:00Z; known10:01Z; last refresh11:00Z/expiry15:00Z; evaluate16:01Z. Invent explicit receipts at14:50Z for ALL inventoried producers including manual/Hermes/direct paths fenced, zero in-flight, registry invalidation14:51Z, cache invalidation14:52Z and per-consumer adoption14:53Z; no overlaps/NULL rows. Pin the finite inventory and receipt coverage and show what this establishes only within the synthetic universe. Expiry-only reasoning must still be rejected; production coverage remains UNKNOWN. |

Expand all dates to full ISO-8601 (synthetic year2026, month01). Clock ordering and boundary semantics must be explicit and internally consistent. The four-hour TTL above is only a challenge parameter, not a production freshness/grace/default policy. Do not invent numeric grace, denominator, freshness threshold, subscriber/adoption defaults or production policy. If a decision needs an unbound policy, mark POLICY_UNCONFIGURED and identify the exact missing binding; preserve known unsafe eligibility separately. Policy gaps should name the required proof/decision and retained owner category, not assign new implementation or a user credential chore.

## Scope and acceptance

Pass: at most8 coherent fixed-clock cases, machine-readable fields and explicit UNKNOWN/null distinctions; both barriers independent; all five unsafe mechanisms covered; both renewal routes inventoried; a concrete counterexample to four-hour-only retirement; a positive synthetic receipt control with finite coverage; concise missing-policy/proof list. A claim of production adoption, freshness or retirement is a failure.

Invented data only: no current provider/market/account/position data, secrets, PHI, labels/outcomes or private publications. Public delayed data is not an extra privacy blocker; no such acquisition is needed. Do not rescreen identical hashes.

No repo application edits, source-code audit, runtime commands, production queries, DB/service/provider actions, live data, security/webhook/schedule changes, scoring/weights/evaluation/held inputs, deployment/merge, paid jobs or GRID_ALLOW_PAID_LLM changes. No Gemini work. Existing persistent webhook remains unchanged. Return a source commit, exact task ID, claimed scope and response link through the same PR2 route. Reviewer will assess that response independently; no response or execution claim follows from publishing this request.
