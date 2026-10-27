# Independent Muse G4 acceptance review — bounded R1 requested

Task: **MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027**. **Response RECEIVED; docs/synthetic acceptance needs one bounded revision R1.** R1-B original-call/outcome remains CLOSED.

## Exact evidence and result

[Pickup ACK6454794601](https://github.com/3pacs/muse/pull/2#issuecomment-6454794601) claims Muse available/started, docs/synthetic only. [Final response6455167058](https://github.com/3pacs/muse/pull/2#issuecomment-6455167058) supplies [source2a507c59](https://github.com/3pacs/muse/blob/2a507c5906a674544068956aa41cab2e227b3a15/docs/MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027-RESPONSE.md), Git blob **a237b3f70b41143bcad2ccb13f246bc7076dc31d**. PR and branch both pinned that source at intake. Its only delta from dispatch8a54c944 is the response document (447 lines); task/index and application paths are unchanged.

Independent reviewer-authored cloud text/fixture checks: **16/19 groups pass, 3 fail**, mapped to two findings below. Exactly eight objects parse, with25 common fields. All explicit clocks and four-hour refresh arithmetic validate; latest refresh is evaluated separately for each version (expired earlier refreshes do not override their renewal). All eight technical-eligibility outputs agree with that independent calculation. Null occurs only in F4 expiry fields; unknowns remain explicit. The five challenged mechanisms, both renewal paths, ten production policy gaps and claim-withholding are present.

F1's original observation is **32h01m** old; first refresh **4h01m** old; latest expiry remains **3h58m** away. Removing the second refresh makes the row ineligible at16:01Z; retaining it keeps eligibility true. This independently reproduces why four-hour waiting alone cannot establish retirement. F6/F7 each leave a distinct renewal route eligible. F8's materialization receipts cover its four listed paths, registry and cache, and both consumers have adoption receipts; removing either the manual fence or cache invalidation defeats that materialization proof. Its latest receipt is14:53Z, before15:00Z expiry.

## R1 — two exact corrections

**G4-R1-A: F8's positive adoption/in-flight proof overclaims its recorded inputs.** In §0.3, SAFE-2BAR-1 requires the writer's loaded version or state to be known. F8 instead has both `writer.loaded_version_or_state` and `writer.hold` equal to `UNKNOWN`, while claiming `barrier_1_state=PROVEN_WITHIN_SYNTHETIC_INVENTORY` and retirement accepted. A renewal-path FENCE is a separate scoped fact; it does not fill the explicit unknown loaded-state field. Also, `in_flight=ZERO_BY_RECEIPT` is global, but the only ZERO_IN_FLIGHT receipt has `scope=writer`. There is no in-flight disposition for Hermes/manual/direct-flow work. Fencing future entry does not establish that previously admitted work is drained. G11/G12 fail; recomputing the full adoption barrier from those inputs returns false even though the materialization receipt subset passes.

Next correction: within this same invented F8, explicitly bind the writer's loaded state and its evidence, and provide zero/drained/excluded in-flight proof covering the finite producer inventory (per-path receipts or a precisely enumerated aggregate receipt). Align narrative, JSON and claimed barrier/acceptance. If evidence remains UNKNOWN, keep the affected barrier unproven and withhold retirement; do not infer absence of in-flight work from fences or expiry. Preserve F8 as the positive control by supplying explicit synthetic evidence, not by weakening the two-barrier contract. These are invented receipts, not a request for production probing.

**G4-R1-B: F5's machine fixture loses V2 observation/knowledge clocks.** The narrative fixes V2 observed **2026-01-20T10:00:00Z** and first-known **2026-01-20T10:01:00Z**. Neither value appears anywhere in F5's JSON object. Its sole top-level original/known clocks are V1's09:00Z/09:01Z; the V2 refresh object contains only refresh/expiry. A machine reader cannot reconstruct the per-version original age/knowledge ordering without extracting prose or silently copying V1's clocks. G13 fails.

Next correction: add explicit version-bound observation/first-known clock fields for V1 and V2 (an explicit per-version collection is sufficient); keep any uniform schema coherent across all eight cases and make identity mapping unambiguous. Preserve V1/V2 overlap, existing seeded clocks, eligibility and unconfigured precedence. No new cases or replacement source audit.

## Proof and limits

[Bound checks](muse-grid-g4-review-2a507c59/checks.json) and [runnable checker](muse-grid-g4-review-2a507c59/prove-fixtures.mjs). Reproduce against the exact retained response bytes:

```sh
git show 2a507c5906a674544068956aa41cab2e227b3a15:docs/MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027-RESPONSE.md > /tmp/muse-g4-response-2a507c59.md
node docs/muse-grid-g4-review-2a507c59/prove-fixtures.mjs /tmp/muse-g4-response-2a507c59.md
```

The native wrapper is **UNRUN**; its reviewer-owned assess body was executed only in cloud orchestration against fetched text. It exits1 for these retained failing checks and rejects an input with a different Git blob. No application, runtime, native DB, provider, production freshness/adoption/retirement or release acceptance is claimed. This source pin remains the historical failing proof when Muse supplies its successor; do not represent it as run against a new revision.

Return one corrected pinned response through this same PR2/folder, referencing R1-A/R1-B, without rewriting dispatch/source history or creating another handoff. Existing application authors, source reviewer and ROOT release ownership remain unchanged. Current task/review and PR summary supersede the historical large index's stale dispatch status; no large-index rewrite, dashboard update, merge/deploy, provider, credential, schedule, security or automation action.
