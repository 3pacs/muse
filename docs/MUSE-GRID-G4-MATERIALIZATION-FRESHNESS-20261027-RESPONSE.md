# MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027 — Response

- **Task ID:** MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027
- **From:** Muse — response document. The pickup ACK was posted separately as PR #2 comment `6454794601`; this document is the response only and makes no acknowledgement claim of its own.
- **Date:** 2026-10-27
- **Source pin:** task doc `docs/MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027.md` at `8a54c944dcfc1b1d3c8861e01c901291b09ba027`, dispatched in PR #2 comment `6453712595`.
- **Scope boundary:** Synthetic/docs only. Every snapshot, version, consumer, path, receipt, and clock below is invented. Nothing here asserts anything about any production system: no production adoption, freshness, retirement, coverage, or behaviour is claimed anywhere in this document. The four-hour TTL appearing in the seeds is a challenge parameter of the fixtures, not a production freshness, grace, or default policy.

---

## 0. Synthetic universe and named rules

### 0.1 JSON and fact conventions

- The string `"UNKNOWN"` means the fact was not supplied in the fixture. Each refresh object in §3 carries `expires_at_before` — the expiry in force immediately before that refresh — as `"UNKNOWN"` wherever the seed supplies no earlier expiry (F1's second refresh is the exception: its before-value is the first refresh's `2026-01-20T16:00:00Z` expiry). An absent receipt is `UNKNOWN` — it is never rendered as false, zero, "fenced", or "adopted".
- JSON `null` appears **only** for an explicitly-null `expires_at` (Case F4, and nowhere else). A null expiry is a *known* fact — "no expiry was set" — and is never conflated with an unknown clock.
- Every case object in §3 uses one identical field schema. Receipts appear in a `receipts` array (empty where a case has none).
- Technical eligibility under a named unsafe rule (`eligible_under_named_rule`) is kept strictly separate from acceptance under the safe contract (`safe_contract_acceptance`). A row can be selector-eligible under an unsafe rule and still be `NOT_ACCEPTED` — that separation is the point of every case except F8.

### 0.2 Unsafe synthetic rules under challenge

These invented rules are the mechanisms the seeds imply. They are named so each case can cite exactly which one it falsifies. None of them is a safe contract, and none is asserted to exist in production.

| Rule ID | Unsafe rule | Falsified by |
|---|---|---|
| `UNSAFE-REFRESH-TTL-1` | **Refresh-only TTL selector.** Each refresh sets `expires_at = refreshed_at + 4h`; the selector consults only the latest `expires_at` and ignores the age of the original observation entirely. | F1 (also the eligibility mechanism in F2, F3, F6, F7) |
| `UNSAFE-NULL-ELIGIBLE-1` | **NULL accepted as eligible.** A selector treats `expires_at = null` as eligible — effectively "no expiry, therefore never expires". | F4 |
| `UNSAFE-HOLD-GLOBAL-1` | **Writer-HOLD-treated-as-global-fence inference.** A known writer HOLD is read as proof that registry, direct-flow, refresher, manual, and cache paths are all fenced. | F2 (and the fence displays in F6, F7) |
| `UNSAFE-EMPTY-RETRACT-1` | **Empty-register-treated-as-retraction inference.** A registration call carrying empty input is read as retracting rows registered earlier, even though the call is a no-op on empty input. | F3 |
| `UNSAFE-LATEST-WINS-1` | **Latest-version-wins inference.** Registering a newer version is read as removing, superseding, and replacing the older version everywhere, including in consumer caches. | F5 |

### 0.3 The safe two-barrier contract they are measured against

`SAFE-2BAR-1` — a retirement claim for a materialized row is accepted **only** when both barriers are proven separately, with receipts, inside a finite named inventory:

- **Barrier 1 (loaded / in-flight / adoption):** the writer's loaded version or state is known; in-flight work has an explicit disposition (a zero-in-flight receipt, not an absence of news); and **each** inventoried consumer has either an adoption receipt or an exclusion proof. Cache presence alone is not adoption.
- **Barrier 2 (materialization / retirement):** every registry row for the snapshot (including overlapping versions and NULL-expiry rows) has an explicit invalidation/retraction disposition; caches have an invalidation disposition; and **every** inventoried renewal path — writer, Hermes refresher, manual API, direct-flow — is shown fenced, so no eligible renewal remains that could resurrect the row.

Neither barrier's evidence substitutes for the other, and elapsed time substitutes for neither.

### 0.4 Boundary semantics — named synthetic assumption only

`SYN-BOUNDARY-1` — in this fixture universe only, a row is selector-eligible **iff `evaluated_at < expires_at`**. No grace is applied anywhere in any case. This is a named synthetic assumption adopted for determinism; it binds nothing in production. Any production grace, TTL, boundary, or precedence value is **`POLICY_UNCONFIGURED`** (see §4, GAP-10).

---

## 1. The two-barrier evidence model

A user deciding whether an old materialization is *gone* needs to see two independent bodies of evidence, because they fail independently.

**Barrier 1 — loaded / in-flight / adoption.** What must be visible: the version the writer has loaded (or its explicit state, e.g. HOLD); the disposition of in-flight work (completed, fenced, or a zero-in-flight receipt — not silence); and, per consumer, either proof that the consumer adopted the successor state/invalidation or proof that the consumer is excluded from serving the old row. A writer can be perfectly fenced while a consumer keeps serving a cached old row (F2, F5): barrier 1 is about *who can still act on or serve the old state*, and only per-consumer receipts answer it.

**Barrier 2 — materialization / retirement.** What must be visible: the registry rows that exist for the snapshot, including overlaps and NULL-expiry rows; the state of every renewal path that could extend those rows (writer, Hermes refresher, an authenticated manual API, direct-flow); the disposition of caches; explicit invalidation/retraction receipts for rows and caches; and proof that no eligible renewal remains. A registry can be emptied on paper while a refresher quietly renews the row an hour later (F1, F6, F7): barrier 2 is about *whether the materialized thing and every way of reviving it are actually closed*.

**Why neither proves the other.** Barrier 1 evidence says nothing about rows already materialized or paths still able to renew them; barrier 2 evidence says nothing about what a writer has loaded or what a consumer is serving. A single green light that merges them will be wrong in exactly the cases below: each case keeps `barrier_1_state` and `barrier_2_state` separate, and the safe disposition withholds any claim whose barrier is unproven.

---

## 2. The eight cases

All clocks are invented, UTC, synthetic January 2026, expanded to full ISO-8601. Snapshot identity is retained across refreshes in every case.

### F1 — Renewed old observation

- **Pinned inputs:** `SNAP_F1` / `V1`. Observed `2026-01-19T08:00:00Z`, first known `2026-01-19T08:01:00Z`. Refresh `2026-01-20T12:00:00Z` → expiry `2026-01-20T16:00:00Z`; refresh again `2026-01-20T15:59:00Z` → expiry `2026-01-20T19:59:00Z`. Evaluated `2026-01-20T16:01:00Z`. Same snapshot ID throughout.
- **Clock check:** at evaluation the first refresh is 4h01m old and 1 minute past its own expiry; the original observation is 32h01m old. The second refresh — fired 1 minute before the first expiry — has already renewed the row.
- **Barrier states:** Barrier 1 `UNPROVEN` (writer, in-flight, and consumer facts are all `UNKNOWN`). Barrier 2 `NOT_RETIRED` — the row is renewed and selector-eligible until `2026-01-20T19:59:00Z` under `UNSAFE-REFRESH-TTL-1` and `SYN-BOUNDARY-1` (16:01 < 19:59).
- **User-visible label:** `NOT RETIRED — RENEWED; ORIGINAL OBSERVATION 32H01M OLD`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED` under `SAFE-2BAR-1`. Withheld: retirement, freshness, and any claim that elapsed TTL retires a renewable row.
- **Minimal proof still missing:** fence receipts for every renewal path; registry and cache invalidation receipts; per-consumer adoption/exclusion proof; a bound original-age ceiling (GAP-01).
- **Failing display:** `RETIRED — 4H TTL ELAPSED (16:01Z)`. **Falsified by:** the `2026-01-20T15:59:00Z` refresh renewed the expiry to `2026-01-20T19:59:00Z` before the first expiry lapsed, so at evaluation the row is selector-eligible. Elapsed time since the first refresh is not retirement proof while renewal remains eligible — this is the concrete counterexample to four-hour-only retirement.

### F2 — Writer HOLD only

- **Pinned inputs:** `SNAP_F2` / `V1`. Observed `2026-01-20T10:00:00Z`, first known `2026-01-20T10:01:00Z`. Refresh `2026-01-20T12:00:00Z` → expiry `2026-01-20T16:00:00Z`. Evaluated `2026-01-20T12:30:00Z`. Writer HOLD is a known fact; in-flight is `UNKNOWN`; registry and direct-flow paths are OPEN; subscriber adoption is `UNKNOWN`; the subscriber cache contains the old row.
- **Barrier states:** Barrier 1 `PARTIAL_WRITER_HOLD_ONLY` — the HOLD is real but covers the writer only; in-flight disposition and consumer adoption are unproven. Barrier 2 `NOT_RETIRED` — registry and direct-flow paths remain open and the cached old row has no invalidation disposition.
- **User-visible label:** `NOT RETIRED — WRITER HOLD ONLY`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: "all paths fenced", retirement, and any adoption claim. The row remains selector-eligible under `UNSAFE-REFRESH-TTL-1` (12:30 < 16:00).
- **Minimal proof still missing:** registry and direct-flow fence receipts; in-flight disposition; cache invalidation receipt; per-consumer adoption/exclusion proof.
- **Failing display:** `ALL PATHS FENCED — WRITER ON HOLD`. **Falsified by:** the pinned inputs state registry and direct-flow paths OPEN and the cache still containing the old row. A HOLD fences nothing beyond the writer; `UNSAFE-HOLD-GLOBAL-1` is an inference, not a fact in this fixture.

### F3 — Empty register

- **Pinned inputs:** `SNAP_F3` / `V1`. Observed `2026-01-20T10:00:00Z`, first known `2026-01-20T10:01:00Z`. Refresh `2026-01-20T11:00:00Z` → expiry `2026-01-20T15:00:00Z`. An empty registration call at `2026-01-20T12:00:00Z` that is a no-op on empty input. Evaluated `2026-01-20T12:01:00Z`. The old registry row and the cache are retained.
- **Barrier states:** Barrier 1 `UNPROVEN` (no writer, in-flight, or consumer facts supplied). Barrier 2 `NOT_RETIRED` — the old row was never retracted, and it remains selector-eligible (12:01 < 15:00).
- **User-visible label:** `NOT RETIRED — EMPTY REGISTER, ROW RETAINED`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: retraction, retirement, and any claim that an empty call changed registry state.
- **Minimal proof still missing:** an explicit retraction/invalidation receipt for the old row; a cache invalidation receipt; a bound empty-register semantics (GAP-06); fence receipts for renewal paths.
- **Failing display:** `RETRACTED — REGISTER EMPTY`. **Falsified by:** the pinned semantics — the `2026-01-20T12:00:00Z` call is a no-op on empty input and the old registry row and cache are retained. Empty input is not retraction; `UNSAFE-EMPTY-RETRACT-1` invents an effect the call does not have.

### F4 — NULL expiry

- **Pinned inputs:** `SNAP_F4` / `V1`. Observed `2026-01-19T08:00:00Z`, first known `2026-01-19T08:01:00Z`. Refresh `2026-01-20T12:00:00Z` with `expires_at` **explicitly null**. Evaluated `2026-01-20T16:01:00Z`.
- **Barrier states:** Barrier 1 `UNPROVEN`. Barrier 2 `NOT_RETIRED` — under `UNSAFE-NULL-ELIGIBLE-1` the row is technically selector-eligible, and no invalidation, fence, or retraction fact exists.
- **User-visible label:** `NOT RETIRED — NULL EXPIRY; POLICY_UNCONFIGURED`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: retirement, automatic expiry, and "eligible indefinitely". The null is a known fact (no expiry was set), distinct from an unknown clock; no automatic expiry may be invented to replace it, and what NULL means for eligibility and retirement is `POLICY_UNCONFIGURED` (GAP-02).
- **Minimal proof still missing:** a bound NULL-expiry semantics; an explicit invalidation/retraction receipt for the row; fence receipts for every renewal path; per-consumer proof.
- **Failing display:** `ELIGIBLE INDEFINITELY — NO EXPIRY SET`. **Falsified by:** the pinned inputs bind no semantics to null at all. The unsafe selector's technical acceptance of null is recorded in `eligible_under_named_rule`, but no policy in this fixture equates "no expiry set" with "never expires" — and the opposite invention (an automatic expiry) is equally unbound.

### F5 — Overlapping versions

- **Pinned inputs:** `SNAP_F5`, versions `V1` and `V2` of the same snapshot. `V1`: observed `2026-01-20T09:00:00Z`, known `2026-01-20T09:01:00Z`, refresh `2026-01-20T11:00:00Z` → expiry `2026-01-20T15:00:00Z`. `V2`: observed `2026-01-20T10:00:00Z`, known `2026-01-20T10:01:00Z`, refresh `2026-01-20T12:00:00Z` → expiry `2026-01-20T16:00:00Z`. Evaluated `2026-01-20T12:30:00Z`. Both versions are in the registry; a subscriber's cache holds `V1`.
- **Barrier states:** Barrier 1 `UNPROVEN` — the subscriber's cache holding `V1` is presence, not adoption or exclusion proof for either version. Barrier 2 `NOT_RETIRED` — both versions are selector-eligible at evaluation (12:30 < 15:00 and 12:30 < 16:00) and neither has an invalidation disposition.
- **User-visible label:** `NOT RETIRED — V1 AND V2 BOTH ELIGIBLE; PRECEDENCE POLICY_UNCONFIGURED`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: "V1 superseded/removed", any precedence claim, and any adoption claim. Version precedence under overlap is `POLICY_UNCONFIGURED` (GAP-03).
- **Minimal proof still missing:** a bound version-precedence rule; a `V1` invalidation/retraction receipt; per-consumer adoption proof for `V2` (or exclusion proof for `V1`).
- **Failing display:** `V2 CURRENT — V1 SUPERSEDED`. **Falsified by:** both versions remain in the registry and selector-eligible at `2026-01-20T12:30:00Z`, and the subscriber cache still holds `V1`. "V2 registered" proves neither V1 removal, precedence, nor adoption; `UNSAFE-LATEST-WINS-1` supplies all three by inference only.

### F6 — Manual path omitted

- **Pinned inputs:** `SNAP_F6` / `V1`. Observed `2026-01-19T08:00:00Z`, first known `2026-01-19T08:01:00Z`. A manual authenticated-API refresh fires `2026-01-20T15:59:00Z`, setting expiry `2026-01-20T19:59:00Z`. Evaluated `2026-01-20T16:01:00Z`. The Hermes path is FENCED; the writer is on HOLD; the manual path is explicitly ELIGIBLE; subscriber evidence is `UNKNOWN`. (Authentication is only a synthetic property of this path, not permission to invoke anything.)
- **Barrier states:** Barrier 1 `PARTIAL_WRITER_HOLD_ONLY` — writer HOLD is known; subscriber evidence is `UNKNOWN`. Barrier 2 `NOT_RETIRED` — a live renewal path remains and has already been exercised at 15:59, renewing the row to 19:59.
- **User-visible label:** `NOT RETIRED — MANUAL PATH STILL ELIGIBLE`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: "all paths fenced", retirement, and any fence-completeness claim drawn from an inventory that omits the manual API.
- **Minimal proof still missing:** a renewal-path inventory that enumerates the manual API (GAP-04); a manual-path fence receipt; per-consumer adoption/exclusion proof.
- **Failing display:** `ALL RENEWAL PATHS FENCED`. **Falsified by:** the manual refresh at `2026-01-20T15:59:00Z` itself — it set expiry `2026-01-20T19:59:00Z` two minutes before evaluation, through a path the fence inventory did not list. An inventory omitting the manual API is incomplete, and its completeness display is false on these inputs.

### F7 — Refresher omitted

- **Pinned inputs:** `SNAP_F7` / `V1`. Observed `2026-01-19T08:00:00Z`, first known `2026-01-19T08:01:00Z`. A Hermes refresher fires `2026-01-20T15:59:00Z`, setting expiry `2026-01-20T19:59:00Z`. Evaluated `2026-01-20T16:01:00Z`. The manual API is FENCED; the writer is on HOLD; the Hermes path is explicitly ELIGIBLE; subscriber evidence is `UNKNOWN`.
- **Barrier states:** Barrier 1 `PARTIAL_WRITER_HOLD_ONLY`. Barrier 2 `NOT_RETIRED` — the Hermes renewal path remains eligible and has already renewed the row to 19:59.
- **User-visible label:** `NOT RETIRED — HERMES PATH STILL ELIGIBLE`.
- **Safe disposition / withheld claims:** `NOT_ACCEPTED`. Withheld: "all paths fenced", retirement, and any completeness claim drawn from closing only the manual route.
- **Minimal proof still missing:** a renewal-path inventory that enumerates the Hermes refresher (GAP-04); a Hermes-path fence receipt; per-consumer adoption/exclusion proof.
- **Failing display:** `ALL RENEWAL PATHS FENCED — MANUAL ROUTE CLOSED`. **Falsified by:** the Hermes refresh at `2026-01-20T15:59:00Z`, which renewed the row to `2026-01-20T19:59:00Z`. Manual-route closure is not a complete renewal fence; this is the mirror image of F6, and a fence standard that catches only one of the two routes fails both cases.

### F8 — Positive proof / boundary control

- **Pinned inputs:** `SNAP_F8` / `V1`. Observed `2026-01-20T10:00:00Z`, first known `2026-01-20T10:01:00Z`. Last refresh `2026-01-20T11:00:00Z` → expiry `2026-01-20T15:00:00Z`. Evaluated `2026-01-20T16:01:00Z`. No overlapping rows, no NULL-expiry rows. The consumer inventory is finite and closed: exactly two consumers, `CONSUMER_A` and `CONSUMER_B`.
- **Invented receipts (all `2026-01-20`):** at `14:50:00Z`, fence receipts for **every** inventoried producer path (writer, Hermes refresher, manual API, direct-flow) plus a zero-in-flight receipt; registry invalidation receipt `14:51:00Z`; cache invalidation receipt `14:52:00Z`; per-consumer adoption receipts `14:53:00Z` for both `CONSUMER_A` and `CONSUMER_B`.
- **Barrier states:** Barrier 1 `PROVEN_WITHIN_SYNTHETIC_INVENTORY` — writer path fenced, zero in-flight receipted, and both inventoried consumers have adoption receipts. Barrier 2 `RETIRED_WITHIN_SYNTHETIC_INVENTORY` — the sole registry row is invalidated, the cache is invalidated, and every inventoried renewal path was fenced before expiry, so no eligible renewal remains inside this universe.
- **User-visible label:** `RETIRED — WITHIN THIS SYNTHETIC INVENTORY ONLY (RECEIPTS COMPLETE 14:53Z)`.
- **Safe disposition / withheld claims:** `ACCEPTED_WITHIN_CLOSED_SYNTHETIC_INVENTORY_ONLY` under `SAFE-2BAR-1`. Withheld: any production retirement, coverage, or adoption claim — production inventory coverage remains `UNKNOWN`. Note the selector fact is recorded separately and proves nothing by itself: under `SYN-BOUNDARY-1` the row is not selector-eligible at evaluation (16:01 is not < 15:00), and that expiry-only fact is **not** the basis of acceptance.
- **Minimal proof still missing:** none inside the closed synthetic inventory. (Any production claim would additionally need a production inventory-coverage attestation — GAP-07 — which is not supplied and not claimed.)
- **Failing display:** `RETIRED — TTL EXPIRED AT 15:00Z`. **Falsified by:** the receipt timeline. Retirement here rests on the receipts — fences and zero-in-flight at `14:50:00Z`, registry invalidation `14:51:00Z`, cache invalidation `14:52:00Z`, consumer adoption complete `14:53:00Z` — all *before* the `15:00:00Z` expiry. An expiry-only display would assert the same conclusion in F1's shape, where it is false; expiry-only reasoning is rejected even in the positive control.

---

## 3. Machine-readable fixture table

One schema across all eight objects. `eligible_under_named_rule` records technical eligibility under the named unsafe rule only; `safe_contract_acceptance` records the separate `SAFE-2BAR-1` verdict. `"UNKNOWN"` means the fact was not supplied; JSON `null` appears only for F4's explicitly-null expiry. F5 has two live versions, so its single `expires_at_at_evaluation` field lists both (`V1:...|V2:...`); the per-version values also appear in its `refreshes` array.

```json
[
  {
    "case_id": "F1",
    "snapshot_id": "SNAP_F1",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T16:01:00Z",
    "original_observed_at": "2026-01-19T08:00:00Z",
    "first_known_at": "2026-01-19T08:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T12:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T16:00:00Z"},
      {"version_id": "V1", "refreshed_at": "2026-01-20T15:59:00Z", "expires_at_before": "2026-01-20T16:00:00Z", "expires_at": "2026-01-20T19:59:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T19:59:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "UNKNOWN"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "UNKNOWN"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "UNKNOWN",
    "renewal_paths": {"writer": "UNKNOWN", "hermes_refresher": "UNKNOWN", "manual_api": "UNKNOWN", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "UNPROVEN",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — RENEWED; ORIGINAL OBSERVATION 32H01M OLD",
    "safe_disposition": "Withhold retirement and freshness; row is renewed and selector-eligible until 2026-01-20T19:59:00Z.",
    "withheld_claims": ["retirement", "freshness", "elapsed-TTL retirement"],
    "minimal_proof_missing": ["fence receipts for every renewal path", "registry invalidation receipt", "cache invalidation receipt", "per-consumer adoption or exclusion proof", "bound original-age ceiling (GAP-01)"],
    "failing_display": {"display": "RETIRED — 4H TTL ELAPSED (16:01Z)", "falsified_by": "The 2026-01-20T15:59:00Z refresh renewed expiry to 2026-01-20T19:59:00Z, so at 2026-01-20T16:01:00Z the row is selector-eligible and the original observation is 32h01m old."},
    "receipts": []
  },
  {
    "case_id": "F2",
    "snapshot_id": "SNAP_F2",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-HOLD-GLOBAL-1", "UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T12:30:00Z",
    "original_observed_at": "2026-01-20T10:00:00Z",
    "first_known_at": "2026-01-20T10:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T12:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T16:00:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T16:00:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "HOLD"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "SNAP_F2_V1"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "CONTAINS_OLD_ROW",
    "renewal_paths": {"writer": "HOLD", "hermes_refresher": "UNKNOWN", "manual_api": "UNKNOWN", "direct_flow": "OPEN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "PARTIAL_WRITER_HOLD_ONLY",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — WRITER HOLD ONLY",
    "safe_disposition": "Credit the writer HOLD only; withhold any fence, adoption, or retirement claim for every other path.",
    "withheld_claims": ["all paths fenced", "retirement", "consumer adoption"],
    "minimal_proof_missing": ["registry fence receipt", "direct-flow fence receipt", "in-flight disposition", "cache invalidation receipt", "per-consumer adoption or exclusion proof"],
    "failing_display": {"display": "ALL PATHS FENCED — WRITER ON HOLD", "falsified_by": "Registry and direct-flow paths are pinned OPEN, in-flight is UNKNOWN, and the subscriber cache contains the old row; the HOLD covers the writer only."},
    "receipts": []
  },
  {
    "case_id": "F3",
    "snapshot_id": "SNAP_F3",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-EMPTY-RETRACT-1", "UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T12:01:00Z",
    "original_observed_at": "2026-01-20T10:00:00Z",
    "first_known_at": "2026-01-20T10:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T11:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T15:00:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T15:00:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "UNKNOWN"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "SNAP_F3_V1"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "RETAINED_OLD_ROW",
    "renewal_paths": {"writer": "UNKNOWN", "hermes_refresher": "UNKNOWN", "manual_api": "UNKNOWN", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "UNPROVEN",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — EMPTY REGISTER, ROW RETAINED",
    "safe_disposition": "Record the empty registration call as a no-op; withhold retraction and retirement.",
    "withheld_claims": ["retraction", "retirement", "registry changed by empty call"],
    "minimal_proof_missing": ["explicit retraction or invalidation receipt for the old row", "cache invalidation receipt", "bound empty-register semantics (GAP-06)", "fence receipts for every renewal path"],
    "failing_display": {"display": "RETRACTED — REGISTER EMPTY", "falsified_by": "The 2026-01-20T12:00:00Z registration call is a no-op on empty input; the old registry row and cache are retained and the row is selector-eligible until 2026-01-20T15:00:00Z."},
    "receipts": []
  },
  {
    "case_id": "F4",
    "snapshot_id": "SNAP_F4",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-NULL-ELIGIBLE-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1", "POLICY_UNCONFIGURED"],
    "evaluated_at": "2026-01-20T16:01:00Z",
    "original_observed_at": "2026-01-19T08:00:00Z",
    "first_known_at": "2026-01-19T08:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T12:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": null}
    ],
    "expires_at_at_evaluation": null,
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "UNKNOWN"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "UNKNOWN"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "UNKNOWN",
    "renewal_paths": {"writer": "UNKNOWN", "hermes_refresher": "UNKNOWN", "manual_api": "UNKNOWN", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-NULL-ELIGIBLE-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "UNPROVEN",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — NULL EXPIRY; POLICY_UNCONFIGURED",
    "safe_disposition": "Record the expiry as explicitly null (a known fact); withhold retirement, automatic expiry, and indefinite eligibility; NULL semantics are POLICY_UNCONFIGURED.",
    "withheld_claims": ["retirement", "automatic expiry", "eligible indefinitely", "NULL-expiry eligibility semantics"],
    "minimal_proof_missing": ["bound NULL-expiry semantics (GAP-02)", "explicit invalidation or retraction receipt", "fence receipts for every renewal path", "per-consumer adoption or exclusion proof"],
    "failing_display": {"display": "ELIGIBLE INDEFINITELY — NO EXPIRY SET", "falsified_by": "expires_at is explicitly null, a known fact with no bound semantics in this fixture; no policy equates null with never-expires, and no automatic expiry may be invented in its place."},
    "receipts": []
  },
  {
    "case_id": "F5",
    "snapshot_id": "SNAP_F5",
    "version_id": "V1_AND_V2",
    "policy_rule_ids": ["UNSAFE-LATEST-WINS-1", "UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1", "POLICY_UNCONFIGURED"],
    "evaluated_at": "2026-01-20T12:30:00Z",
    "original_observed_at": "2026-01-20T09:00:00Z",
    "first_known_at": "2026-01-20T09:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T11:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T15:00:00Z"},
      {"version_id": "V2", "refreshed_at": "2026-01-20T12:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T16:00:00Z"}
    ],
    "expires_at_at_evaluation": "V1:2026-01-20T15:00:00Z|V2:2026-01-20T16:00:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "UNKNOWN"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "SNAP_F5_V1"}
    ],
    "registry": {"rows": ["V1", "V2"], "overlaps": ["V1+V2"]},
    "cache_disposition": "CONTAINS_V1",
    "renewal_paths": {"writer": "UNKNOWN", "hermes_refresher": "UNKNOWN", "manual_api": "UNKNOWN", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "UNPROVEN",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — V1 AND V2 BOTH ELIGIBLE; PRECEDENCE POLICY_UNCONFIGURED",
    "safe_disposition": "Show both versions as registered and selector-eligible; withhold precedence, removal, and adoption claims.",
    "withheld_claims": ["V1 superseded or removed", "version precedence", "consumer adoption of V2"],
    "minimal_proof_missing": ["bound version-precedence rule (GAP-03)", "V1 invalidation or retraction receipt", "per-consumer adoption proof for V2 or exclusion proof for V1"],
    "failing_display": {"display": "V2 CURRENT — V1 SUPERSEDED", "falsified_by": "Both V1 and V2 are in the registry and selector-eligible at 2026-01-20T12:30:00Z, and the subscriber cache holds V1; registration of V2 proves neither V1 removal, precedence, nor adoption."},
    "receipts": []
  },
  {
    "case_id": "F6",
    "snapshot_id": "SNAP_F6",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-HOLD-GLOBAL-1", "UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T16:01:00Z",
    "original_observed_at": "2026-01-19T08:00:00Z",
    "first_known_at": "2026-01-19T08:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T15:59:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T19:59:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T19:59:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "HOLD"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "UNKNOWN"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "UNKNOWN",
    "renewal_paths": {"writer": "HOLD", "hermes_refresher": "FENCED", "manual_api": "ELIGIBLE", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "PARTIAL_WRITER_HOLD_ONLY",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — MANUAL PATH STILL ELIGIBLE",
    "safe_disposition": "Withhold any fence-completeness or retirement claim; the manual API path is eligible and already renewed the row.",
    "withheld_claims": ["all renewal paths fenced", "retirement", "fence-inventory completeness"],
    "minimal_proof_missing": ["renewal-path inventory enumerating the manual API (GAP-04)", "manual-path fence receipt", "per-consumer adoption or exclusion proof"],
    "failing_display": {"display": "ALL RENEWAL PATHS FENCED", "falsified_by": "The manual authenticated-API refresh at 2026-01-20T15:59:00Z set expiry 2026-01-20T19:59:00Z; the fence inventory omitted the manual path that was explicitly ELIGIBLE."},
    "receipts": []
  },
  {
    "case_id": "F7",
    "snapshot_id": "SNAP_F7",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-HOLD-GLOBAL-1", "UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T16:01:00Z",
    "original_observed_at": "2026-01-19T08:00:00Z",
    "first_known_at": "2026-01-19T08:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T15:59:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T19:59:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T19:59:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "HOLD"},
    "in_flight": "UNKNOWN",
    "consumers": [
      {"id": "UNKNOWN", "adoption_state": "UNKNOWN", "cache_content": "UNKNOWN"}
    ],
    "registry": {"rows": ["V1"], "overlaps": []},
    "cache_disposition": "UNKNOWN",
    "renewal_paths": {"writer": "HOLD", "hermes_refresher": "ELIGIBLE", "manual_api": "FENCED", "direct_flow": "UNKNOWN"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": true},
    "safe_contract_acceptance": "NOT_ACCEPTED",
    "barrier_1_state": "PARTIAL_WRITER_HOLD_ONLY",
    "barrier_2_state": "NOT_RETIRED",
    "user_visible_label": "NOT RETIRED — HERMES PATH STILL ELIGIBLE",
    "safe_disposition": "Withhold any fence-completeness or retirement claim; the Hermes refresher is eligible and already renewed the row.",
    "withheld_claims": ["all renewal paths fenced", "retirement", "fence-inventory completeness"],
    "minimal_proof_missing": ["renewal-path inventory enumerating the Hermes refresher (GAP-04)", "Hermes-path fence receipt", "per-consumer adoption or exclusion proof"],
    "failing_display": {"display": "ALL RENEWAL PATHS FENCED — MANUAL ROUTE CLOSED", "falsified_by": "The Hermes refresh at 2026-01-20T15:59:00Z set expiry 2026-01-20T19:59:00Z; closing the manual route does not fence the Hermes refresher, which was explicitly ELIGIBLE."},
    "receipts": []
  },
  {
    "case_id": "F8",
    "snapshot_id": "SNAP_F8",
    "version_id": "V1",
    "policy_rule_ids": ["UNSAFE-REFRESH-TTL-1", "SYN-BOUNDARY-1", "SAFE-2BAR-1"],
    "evaluated_at": "2026-01-20T16:01:00Z",
    "original_observed_at": "2026-01-20T10:00:00Z",
    "first_known_at": "2026-01-20T10:01:00Z",
    "refreshes": [
      {"version_id": "V1", "refreshed_at": "2026-01-20T11:00:00Z", "expires_at_before": "UNKNOWN", "expires_at": "2026-01-20T15:00:00Z"}
    ],
    "expires_at_at_evaluation": "2026-01-20T15:00:00Z",
    "writer": {"loaded_version_or_state": "UNKNOWN", "hold": "UNKNOWN"},
    "in_flight": "ZERO_BY_RECEIPT",
    "consumers": [
      {"id": "CONSUMER_A", "adoption_state": "ADOPTION_RECEIPT_2026-01-20T14:53:00Z", "cache_content": "INVALIDATED"},
      {"id": "CONSUMER_B", "adoption_state": "ADOPTION_RECEIPT_2026-01-20T14:53:00Z", "cache_content": "INVALIDATED"}
    ],
    "registry": {"rows": [], "overlaps": []},
    "cache_disposition": "INVALIDATED_BY_RECEIPT_2026-01-20T14:52:00Z",
    "renewal_paths": {"writer": "FENCED", "hermes_refresher": "FENCED", "manual_api": "FENCED", "direct_flow": "FENCED"},
    "eligible_under_named_rule": {"rule": "UNSAFE-REFRESH-TTL-1", "eligible": false},
    "safe_contract_acceptance": "ACCEPTED_WITHIN_CLOSED_SYNTHETIC_INVENTORY_ONLY",
    "barrier_1_state": "PROVEN_WITHIN_SYNTHETIC_INVENTORY",
    "barrier_2_state": "RETIRED_WITHIN_SYNTHETIC_INVENTORY",
    "user_visible_label": "RETIRED — WITHIN THIS SYNTHETIC INVENTORY ONLY (RECEIPTS COMPLETE 14:53Z)",
    "safe_disposition": "Accept retirement inside this closed synthetic inventory only, on the receipts (complete 2026-01-20T14:53:00Z, before expiry); withhold every production claim.",
    "withheld_claims": ["production retirement", "production inventory coverage", "production adoption"],
    "minimal_proof_missing": [],
    "failing_display": {"display": "RETIRED — TTL EXPIRED AT 15:00Z", "falsified_by": "Expiry alone proves nothing: the claim rests on fence and zero-in-flight receipts at 2026-01-20T14:50:00Z, registry invalidation 2026-01-20T14:51:00Z, cache invalidation 2026-01-20T14:52:00Z, and consumer adoption receipts 2026-01-20T14:53:00Z — all before the 2026-01-20T15:00:00Z expiry; the same expiry-only display in F1 is false."},
    "receipts": [
      {"type": "FENCE", "scope": "writer", "at": "2026-01-20T14:50:00Z"},
      {"type": "FENCE", "scope": "hermes_refresher", "at": "2026-01-20T14:50:00Z"},
      {"type": "FENCE", "scope": "manual_api", "at": "2026-01-20T14:50:00Z"},
      {"type": "FENCE", "scope": "direct_flow", "at": "2026-01-20T14:50:00Z"},
      {"type": "ZERO_IN_FLIGHT", "scope": "writer", "at": "2026-01-20T14:50:00Z"},
      {"type": "REGISTRY_INVALIDATION", "scope": "SNAP_F8_V1", "at": "2026-01-20T14:51:00Z"},
      {"type": "CACHE_INVALIDATION", "scope": "cache", "at": "2026-01-20T14:52:00Z"},
      {"type": "CONSUMER_ADOPTION", "scope": "CONSUMER_A", "at": "2026-01-20T14:53:00Z"},
      {"type": "CONSUMER_ADOPTION", "scope": "CONSUMER_B", "at": "2026-01-20T14:53:00Z"}
    ]
  }
]
```

---

## 4. Policy-gap list

Each gap names the exact missing binding or proof and the retained owner **category** that must supply it. Until a gap is bound, the dependent behaviour is `POLICY_UNCONFIGURED` and the dependent claim is withheld. No gap assigns new implementation work.

- **GAP-01 — Original-age ceiling independent of refreshes.** Missing binding: a maximum admissible age of the *original observation*, which no number of refreshes may extend, and the selector behaviour when it is exceeded. Owner: GRID policy owner.
- **GAP-02 — NULL-expiry semantics.** Missing binding: what an explicitly-null `expires_at` means for selector eligibility and retirement (never-eligible, never-expires, or must-invalidate), stated so null is never silently read as either extreme. Owner: GRID policy owner.
- **GAP-03 — Version precedence under overlap.** Missing binding: the rule deciding which of two simultaneously eligible versions governs, and what registration of a successor does and does not do to the predecessor's registry row and to consumer caches. Owner: GRID policy owner.
- **GAP-04 — Renewal-path inventory completeness standard.** Missing binding: the standard a fence claim must meet — the inventory must enumerate, at minimum, the writer, the Hermes refresher, the manual authenticated API, and direct-flow paths, each with an individual fence state; a claim over a partial inventory is not a fence claim (F6, F7). Owner: GRID policy owner (standard); GRID authors / exact-source reviewer (inventory evidence).
- **GAP-05 — HOLD scope and display semantics.** Missing binding: the declared scope of a writer HOLD (which paths it does and does not fence) and the display rule that a HOLD may only ever be rendered as a writer-scoped fact, never as a global fence (F2). Owner: GRID policy owner.
- **GAP-06 — Empty-register vs retraction semantics.** Missing binding: the specified effect of a registration call with empty input (no-op vs retraction), and the explicit retraction act a caller must perform instead if retraction is intended (F3). Owner: GRID policy owner.
- **GAP-07 — Minimal retirement-proof receipt standard and finite-inventory attestation.** Missing binding: the receipt set a retirement claim requires (per-path fence receipts, zero-in-flight receipt, registry and cache invalidation receipts, per-consumer adoption/exclusion receipts — the F8 shape) and the attestation that the producer/consumer inventory those receipts cover is finite and complete. Owner: controller (acceptance standard).
- **GAP-08 — Consumer adoption vs cache presence.** Missing binding: the definition of adoption evidence (an adoption receipt or an exclusion proof per consumer) and the rule that mere cache presence of a version is evidence of neither adoption nor non-adoption (F2, F5). Owner: GRID policy owner.
- **GAP-09 — Display rules for retirement and freshness.** Missing binding: the rule forbidding a single-barrier green, a writer HOLD, or an elapsed TTL from rendering as `RETIRED` or as fresh; a retirement label requires both barrier states proven, shown separately (F1, F2, F8). Owner: GRID authors / exact-source reviewer.
- **GAP-10 — Exact-expiry boundary and grace semantics.** Missing binding: the behaviour at the exact expiry instant (this response assumes, synthetically only, `SYN-BOUNDARY-1`: eligible iff `evaluated_at < expires_at`) and whether any grace exists, and if so its bound value. Owner: GRID policy owner.

---

## 5. Conformance checklist

Mapping of the task's Pass criteria to where this response satisfies each:

| Pass criterion | Satisfied at |
|---|---|
| At most 8 coherent fixed-clock cases | Exactly 8 cases, F1–F8, §2 narratives and §3 fixtures; all clocks invented January 2026 UTC, expanded to full ISO-8601, arithmetically consistent (F1 ages checked: first refresh 4h01m old and original observation 32h01m old at evaluation) |
| Machine-readable fields | §3: one fenced JSON array, one identical field schema across all 8 objects, parseable as JSON |
| Explicit UNKNOWN / null distinctions | §0.1 conventions; `"UNKNOWN"` for unsupplied facts throughout §3; JSON `null` used only for F4's explicitly-null `expires_at` |
| Both barriers independent | §1 evidence model; separate `barrier_1_state` / `barrier_2_state` in every case; no case lets one barrier's evidence stand in for the other |
| All five unsafe mechanisms covered | `UNSAFE-REFRESH-TTL-1` (F1), `UNSAFE-HOLD-GLOBAL-1` (F2, F6, F7), `UNSAFE-EMPTY-RETRACT-1` (F3), `UNSAFE-NULL-ELIGIBLE-1` (F4), `UNSAFE-LATEST-WINS-1` (F5) — named in §0.2 and cited per case |
| Both renewal routes inventoried | `renewal_paths` in every §3 object enumerates writer, Hermes refresher, manual API, and direct-flow; manual route challenged in F6, Hermes route in F7, both fenced by receipt in F8 |
| Concrete counterexample to four-hour-only retirement | F1: second refresh at 15:59 renews the row to 19:59; at 16:01 the row is eligible and the observation is 32h01m old |
| Positive synthetic receipt control with finite coverage | F8: closed inventory (4 producer paths, exactly 2 named consumers), receipts complete 14:53 before the 15:00 expiry, acceptance scoped to the synthetic inventory only; expiry-only reasoning still rejected |
| Concise missing-policy / proof list | §4, GAP-01–GAP-10, each naming the exact missing binding or proof and its retained owner category |
| No production claim | Header scope boundary; `withheld_claims` in every case; every unbound production decision recorded as `POLICY_UNCONFIGURED` with its missing binding named in §4 |

---

*End of response. Published as `docs/MUSE-GRID-G4-MATERIALIZATION-FRESHNESS-20261027-RESPONSE.md` via the PR #2 route. No GRID source was read, no production data was used, and nothing in this document claims production adoption, freshness, or retirement.*
