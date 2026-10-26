# MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023 — ACK + Response

- **Task ID:** MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023
- **From:** Muse — this document is the combined **ACK and response**. Task accepted as bounded: docs/contract critique + deterministic synthetic fixtures only.
- **Date:** 2026-10-25
- **Source pin:** 3pacs/muse PR #2 head `7191ef8748d015aa5f4b3e67cce839b8c53ed6b3` (task text as dispatched in `docs/MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023.md`).
- **Scope boundary:** No GRID source audit (Codex owns PR903/904 exact-source review). No production data, no provider/network lookup, no application edits, no rescoring, no learned-weight update. All assets, prices, and clocks below are invented fixtures. Nothing here asserts what the current product does or does not implement.
- **Amendment 1 — 2026-10-26:** Controller clarifications (PR #2 comment `6410046097`) incorporated. Q1 resolved: no collapsed headline — invalidation and terminal return are two explicit headline legs (§4). Q2 resolved: production policy values are unverified and must not be invented — dependent behaviour is `POLICY_UNCONFIGURED`, production headline rates/eligibility claims requiring those values are withheld, and the exact production bindings still required are listed as a separate acceptance gate (§4). The original contract, the nine cases, and the negative findings are preserved; Case 6's headline expectation is updated per Q1, and the former `SYN-INV-1` governing-leg assumption is retired.
- **Amendment 2 (R1) — 2026-10-26:** Bounded docs correction answering the independent review at `ac3d33c48a` (`docs/MUSE-GRID-CALL-OUTCOME-ACCEPTANCE-20261023-REVIEW.md`), which found two documentation gaps in the `406c67a9` text. **R1 change map:** (1) Numeric-return invariant `NUM-CLASS-1` added (§0) — one rule distinguishing admitted/scored returns from labelled provisional/candidate arithmetic; contract 2.2, 2.7, 3.2, risks R2/R3, Cases 1/4 and conformance assertion 2 aligned to it (the blanket ban that contradicted Cases 1/4 is replaced). (2) Fixed inputs completed: §(c) fixture table added in machine-readable CSV for all nine groups plus the grace-boundary subcase 3b (equality at 21:10:00Z specified); Case 7 gains `E2` evaluated_at; Case 8 pins W2 learned_at and an exact evaluation clock; Case 9 pins its evaluation clock, C2/C3 fixed inputs, and metric-specific denominators. Original response (`73bb69de`) and Amendment 1 (`406c67a9`) remain in history; nothing else is changed.

---

## 0. Shared fixture and synthetic policy assumptions

**Calendar:** `CAL_SYN_1` — sessions 2026-01-05, 06, 07, 08; session close 21:00Z. No real exchange holidays inferred.

**Reference call C1 (immutable):**

| Field | Value |
|---|---|
| Call ID | `C1` |
| Issued | 2026-01-05T21:01Z |
| Target | `ASSET_X` |
| Direction | LONG (price up) — *synthetic assumption; the seed fixes target/baseline but not direction* |
| Baseline | 100, observed 2026-01-05T21:00Z, first known 2026-01-05T21:00:30Z |
| Benchmark | `BENCH_Y`, baseline 200, observed 2026-01-05T21:00Z, first known 2026-01-05T21:00:30Z |
| Horizon | 2026-01-07T21:00Z (per `CAL_SYN_1`) |
| Invalidation | "An admitted observation at or below 98 during the window" — window = (2026-01-05T21:01Z, 2026-01-07T21:00Z] |
| Weights at issue | `W1` |

**Arithmetic control (exact):** endpoints ASSET_X 102 / BENCH_Y 202 → raw return **+2.00%**, benchmark return **+1.00%**, excess **+1.00pp**. No other arithmetic appears anywhere in this document except where a case states its own endpoint (99 → raw −1.00%, excess −2.00pp; 97 → invalidation only; 98 → raw −2.00% candidate under conflict).

**Labelled synthetic assumptions** (test scaffolding — *not* claims about the product):

- `SYN-GRACE-10` — publication grace is **10 minutes** after horizon. Before horizon+grace with no endpoint: `PENDING-PUBLICATION`. After: `MATURED-UNAVAILABLE`. (The seed mandates the 10-minute value for Case 3; this response applies it fixture-wide for determinism.) *Production grace is unbound — `POLICY_UNCONFIGURED` (§4 gate, item B2).*
- `SYN-RULE-1` — the scoring rule under test in the arithmetic cases: at horizon, raw return = endpoint/baseline − 1; benchmark return likewise; excess = raw − benchmark; the **return leg** is "correct" iff the sign of raw return matches the declared direction. Invalidation is a **separate leg**, never merged into the return leg.
- `SYN-INV-1` — **RETIRED by controller clarification (comment `6410046097`, §4 Q1).** The former assumption (a breached invalidation governs a single headline) is withdrawn: this contract has no single headline classification. Invalidation and terminal return are two explicit headline legs — never collapsed into one win/loss, never selectively hidden, neither leg governing the other. This is presentation guidance for the bounded proposal, **not** a production scoring policy.
- `SYN-SRC-1` — an unresolved equal-standing source conflict blocks scoring entirely (status `CONFLICT`). No averaging, no favourable pick. (Fixture rule; the production source-resolution policy is unbound — `POLICY_UNCONFIGURED`, §4 gate item B1.)
- Fixture completions, flagged where used: Case 1 provisional mark 101; Case 6 benchmark endpoint 202.

**Numeric-return invariant `NUM-CLASS-1` (R1 — the single rule governing every numeric return in this contract):** numeric return arithmetic exists in exactly three classes. **Class A — ADMITTED return:** computed only from an admitted horizon endpoint (contract 2.2); the only class that may be scored, enter any accuracy/return statistic or denominator, or render without a qualifier. **Class B — PROVISIONAL arithmetic:** computed from a pre-horizon mark, always rendered with the literal label `PROVISIONAL — NOT SCORED` and the mark's observed-at (contract 2.3, Case 1). **Class C — CANDIDATE arithmetic:** computed from an unresolved conflicting value, always rendered provider-tagged with the literal label `UNRESOLVED CANDIDATE — NOT SCORED` (contract 2.7, Case 4). Classes B and C are display arithmetic only: they never enter matured counts, accuracy, any denominator, or View 3, and are never styled as a result. Where no observation exists at all (Case 3) or only a stale one (Case 5), **no arithmetic of any class** is rendered. Any numeric return outside these classes, or a class B/C figure rendered without its label, is a contract violation.

**Counting rules (fixture-wide, deterministic):**

| View-2 state | issued | matured | eligible/scored | pending | missing | conflicting | revised |
|---|---|---|---|---|---|---|---|
| `OPEN` | +1 | — | — | +1 | — | — | — |
| `PENDING-PUBLICATION` | +1 | — | — | +1 | — | — | — |
| `MATURED` (endpoint admitted, eligible) | +1 | +1 | +1 | — | — | — | — |
| `MATURED-UNAVAILABLE` | +1 | +1 | — | — | +1 | — | — |
| `CONFLICT` | +1 | +1 | — | — | — | +1 | — |
| `STALE-ONLY` past grace | +1 | +1 | — | — | +1 | — | — |
| Any state, later superseded by a corrected evaluation | as before | as before | per current vintage only | — | — | — | +1 |

Rules: every issued call appears in exactly one state row at any eval clock; the only denominator for any accuracy/return statistic is **eligible/scored under one declared evaluation vintage**; a call is never counted in two vintages at once; `revised` is an overlay count, not a state.

---

## (a) Minimum visible acceptance contract

Three linked views. A field not recorded at the relevant time renders as `NOT RECORDED` / `UNKNOWN` / a named pending state — never backfilled, never zero, never silently omitted.

### View 1 — Original call (immutable after issue)

| # | Minimal visible field | Safe behaviour if unavailable |
|---|---|---|
| 1.1 | Stable call ID | No ID → call is not publishable as a scored call |
| 1.2 | Original text, direction, target — verbatim | Post-hoc rewrites prohibited; edits create a new call ID |
| 1.3 | Issued-at clock (UTC) + calendar ID + timezone basis | Missing issue clock → exclude from all cohorts |
| 1.4 | Baseline value, its observation time, its first-known time, source ID | Baseline without observation time → `NOT RECORDED`, call ineligible |
| 1.5 | Evidence list: per item — source ID, observed-at, available-at; only items with available-at ≤ issued-at may appear | Later evidence is structurally excluded, not merely labelled |
| 1.6 | Horizon instant + calendar ID | No horizon → call can never mature; display `NO HORIZON DECLARED` |
| 1.7 | Invalidation rule verbatim, or the literal label `NOT DECLARED` | `NOT DECLARED` is a first-class display, not a blank |
| 1.8 | Prediction/model version + learned-weight version used at issue, + the data vintage those weights were learned from | Weight version missing → `NOT RECORDED`; current weights must never be substituted here |

### View 2 — Observed outcome

| # | Minimal visible field | Safe behaviour if unavailable |
|---|---|---|
| 2.1 | Maturity state, from a closed state set: `OPEN` (window running) · `PENDING-PUBLICATION` (past horizon, within grace) · `MATURED` (endpoint admitted) · `MATURED-UNAVAILABLE` (past grace, no endpoint) · `CONFLICT` (unresolved source disagreement) · `STALE-ONLY` (only observations older than the horizon exist) | Any data condition not in the set is a contract violation, not a new silent state |
| 2.2 | Endpoint value + source ID + observed-at + first-known-at + vintage ID | No admitted endpoint → **no Class A (admitted/scored) return and no scored metric** (`NUM-CLASS-1`); Class B/C arithmetic may render only under its 2.3/2.7 labels; where no observation exists, no arithmetic of any class |
| 2.3 | Provisional mark (pre-horizon), labelled `PROVISIONAL — NOT SCORED`, with its own observed-at | Provisional (Class B) marks never enter matured counts, accuracy, or any denominator |
| 2.4 | Invalidation coverage: `COMPLETE` / `PARTIAL` / `UNKNOWN` + basis (which path observations were admitted) | Default is `UNKNOWN`; coverage is never upgraded by absence of a breach |
| 2.5 | Invalidation leg result: `BREACHED` (with the breaching observation's value + observed-at) / `NOT BREACHED` (only if coverage = `COMPLETE`) / `UNKNOWN` | `NOT BREACHED` is forbidden unless coverage is `COMPLETE` |
| 2.6 | Staleness: for every displayed price, observed-at is primary; fetch time is secondary and labelled as fetch time; age at horizon is shown for stale items | A price whose observed-at ≠ horizon close must not populate the endpoint field |
| 2.7 | Conflicting values: all competing values shown with provider ID + observed-at + first-known-at; any arithmetic on a competing value is Class C, provider-tagged, labelled `UNRESOLVED CANDIDATE — NOT SCORED` | No value is hidden because it is unfavourable; no candidate figure renders without its Class C label |

### View 3 — Scoring explanation

| # | Minimal visible field | Safe behaviour if unavailable |
|---|---|---|
| 3.1 | Rule ID + version under which the score was produced (e.g. `SYN-RULE-1` in fixtures) | Unversioned score → not displayable as a score |
| 3.2 | Eligibility: `ELIGIBLE` / `INELIGIBLE` + machine-readable reason (e.g. `endpoint_missing`, `source_conflict`, `window_open`) | Ineligible → reason shown, no Class A figures; View 3 never displays Class B/C arithmetic (it lives only in View 2, under its labels) |
| 3.3 | Raw return, benchmark identity + benchmark return, excess — each with its formula inputs (endpoint, baseline, clocks) | Raw and excess are separate lines; excess is never relabelled as raw |
| 3.4 | Instrument convention: index close vs ETF fill vs other, named exactly | An index close labelled as an ETF fill (or vice versa) is a contract violation |
| 3.5 | Two-leg headline: the return leg and the invalidation leg rendered side by side **are** the headline (controller clarification, §4 Q1). No collapsed single verdict exists in this contract | A collapsed win/loss headline, or hiding either leg, is a contract violation |
| 3.6 | Evaluation ID + vintage + evaluated-at + supersedes link to any prior evaluation | Corrections create a new evaluation; the prior one remains reachable and unchanged |
| 3.7 | Cohort context: counts — issued / matured / eligible-scored / pending / missing / conflicting / revised — plus the exact denominator used for any rate | Rate without visible denominator and counts → contract violation |
| 3.8 | Weight provenance: original-call weight version (from View 1) vs current learned-weight version, displayed as distinct roles with their learned-from vintages | Any rescoring under newer weights is labelled `COUNTERFACTUAL — NOT THE ORIGINAL SCORE` |
| 3.9 | Uncertainty statement for any aggregate: n, observation window, and a plain statement that outcome agreement is not proof of profitability or causal value | n = 0 → aggregate renders `UNAVAILABLE`, never 0% or 100% |

---

## (b) Misleading-presentation risks, prioritized, with remedies

**R1 — Provisional gain rendered as a matured win.** An open-window mark (Case 1: +1% on Jan 6) is shown with win styling and/or counted in accuracy before the horizon. *Remedy:* labels and aggregates are gated by the View-2 state machine; only `MATURED` + `ELIGIBLE` records can carry a verdict or enter any accuracy figure; provisional marks carry the literal `PROVISIONAL — NOT SCORED` label.

**R2 — Missing endpoint scored as loss/flat/zero, or the call silently disappears.** Absence of data becomes a numeric outcome, or the row vanishes from every count. *Remedy:* `MATURED-UNAVAILABLE` is a terminal, visible, non-numeric state; the call remains in issued/matured/missing counts permanently; no Class A return may be rendered without an admitted endpoint, and where no observation exists at all, no arithmetic of any class (`NUM-CLASS-1`; contract 2.2, 3.2).

**R3 — Cherry-picking between contradictory sources.** With A = 102 and B = 98 (Case 4), the UI picks the favourable source, or averages them into a fictitious 100. *Remedy:* a declared source/vintage policy is a precondition for scoring; absent one, state = `CONFLICT`, scoring blocked, both values displayed with provenance, and any arithmetic on them rendered only as provider-tagged Class C candidates under `NUM-CLASS-1` (contract 2.7). Averaging conflicting endpoints is prohibited outright.

**R4 — Stale observation masquerading as the endpoint.** Fetch time is presented as observation time, so a Jan 6 close becomes the Jan 7 endpoint (Case 5). *Remedy:* observed-at is the primary timestamp on every price; the endpoint field accepts only observations at the horizon close per the declared calendar; stale items display their age and feed the `STALE-ONLY` state, never the endpoint.

**R5 — Invalidation vs terminal return: double counting and selective legs.** A breached call that ends +2% is shown as a win (breach hidden) or as a clean loss (return erased), whichever flatters the record (Case 6). *Remedy:* mandatory two-leg headline rendering (contract 3.5, §4 Q1); there is no collapsed classification to game — both legs remain visible in headline position at all times.

**R6 — Silent historical rewrite after a correction.** A corrected endpoint (102 → 99, Case 7) overwrites the original evaluation, making the record appear always-correct or always-wrong. *Remedy:* evaluations are vintage-versioned and immutable; a correction spawns a superseding evaluation showing what changed, when it was first known, and the score delta; revised calls are counted as `revised`, never merged invisibly into the original cohort figures.

**R7 — Current learned weights attributed to the original call.** The call page shows W2 (learned after the call) as if C1 were made under W2, or post-issue evidence leaks into the "known then" panel (Case 8). *Remedy:* weight version and evidence set are pinned on the call record at issue and rendered only from that pin (contract 1.5, 1.8, 3.8); any W2-based rescoring is labelled counterfactual.

**R8 — Denominator games and false precision.** n = 0 rendered as 0%/100%; 1/1 rendered as a headline "100% accuracy"; rates computed over issued instead of eligible; an index close labelled an ETF fill (Case 9, contract 3.4). *Remedy:* counts-first display with the denominator always adjacent to any rate; n = 0 → `UNAVAILABLE`; headline rates are suppressed below a declared minimum-n policy (policy value itself must be declared — see §4); instrument convention is a named field, never implied.

---

## (c) Deterministic acceptance matrix — 9 cases

All cases use C1 and the §0 fixture unless a case restates a field. "Eval" = the fixed evaluation clock for the case. A case **passes** only if every "Display" item appears, every "Withhold" item is absent, and eligibility matches exactly.

**Summary matrix (detail per case below):**

| Case | Eval clock (Z) | Expected state | Score eligibility | Denominator effect |
|---|---|---|---|---|
| 1 Open window | 2026-01-06T21:01 | `OPEN` | Ineligible — `window_open` | pending +1 |
| 2 Matured control | 2026-01-07T21:20 | `MATURED` | Eligible, return leg only, `partial_coverage` | scored +1 |
| 3 Missing endpoint | 2026-01-07T21:01 → 21:20 | `PENDING-PUBLICATION` → `MATURED-UNAVAILABLE` | Ineligible — `endpoint_missing` | pending +1 → missing +1 |
| 4 Contradictory sources | 2026-01-07T21:20 | `CONFLICT` | Ineligible — `source_conflict` | conflicting +1 |
| 5 Stale observation | 2026-01-07T21:20 | `STALE-ONLY` → `MATURED-UNAVAILABLE` | Ineligible — `endpoint_missing (stale_only)` | missing +1 |
| 6 Known invalidation | 2026-01-07T21:20 | `MATURED` | Eligible, counted once, two-leg verdict | scored +1 |
| 7 Corrected data | E1 2026-01-07T21:20; V2 known 2026-01-08T12:00; E2 evaluated_at 2026-01-08T12:05 | `MATURED`, evaluation `REVISED` | E1 eligible when produced; E2 is current | revised +1, scored once |
| 8 Learned-weight change | 2026-01-08T12:30 (W2 learned_at 2026-01-08T12:00) | unchanged by W2 | Original (W1) score only | none |
| 9 Zero/partial sample | 2026-01-07T21:20 (exact) | mixed (per call) | 1 of 3 eligible | return-leg scored denominator = 1; invalidation: coverage counts only; empty cohort → `UNAVAILABLE` |

**Machine-readable fixture table (R1 — every fixed input for the nine groups; all clocks UTC, calendar `CAL_SYN_1`, benchmark BENCH_Y baseline 200 obs 2026-01-05T21:00Z known 21:00:30Z SRC_A unless a row restates it):**

```csv
case,call,issued_at,baseline,baseline_obs,baseline_known,src,horizon_at,eval_at,endpoint,endpoint_obs,endpoint_known,endpoint_src,vintage,weights_issue,weights_current,expected_state,expected_reason
1,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-06T21:01Z,PROVISIONAL:101,2026-01-06T21:00Z,2026-01-06T21:00:30Z,SRC_A,V1,W1,W1,OPEN,window_open
2,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,102,2026-01-07T21:00Z,2026-01-07T21:00:30Z,SRC_A,V1,W1,W1,MATURED,eligible_return_leg_only+partial_coverage
3a,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:01Z,ABSENT,,,,,V1,W1,W1,PENDING-PUBLICATION,endpoint_missing
3b,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:10:00Z,ABSENT,,,,,V1,W1,W1,PENDING-PUBLICATION,endpoint_missing+grace_boundary_inclusive
3c,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:10:01Z,ABSENT,,,,,V1,W1,W1,MATURED-UNAVAILABLE,endpoint_missing
3d,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,ABSENT,,,,,V1,W1,W1,MATURED-UNAVAILABLE,endpoint_missing
4,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,"A:102|B:98",2026-01-07T21:00Z,2026-01-07T21:00:30Z,"SRC_A|SRC_B",V1,W1,W1,CONFLICT,source_conflict
5,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,STALE:102,2026-01-06T21:00Z,2026-01-06T21:00:30Z,SRC_A,V1,W1,W1,MATURED-UNAVAILABLE,endpoint_missing(stale_only)
6,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,"102+PATH:97@2026-01-06T21:00Z",2026-01-07T21:00Z,2026-01-07T21:00:30Z,SRC_A,V1,W1,W1,MATURED,eligible_two_leg
7-E1,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,102,2026-01-07T21:00Z,2026-01-07T21:00:30Z,SRC_A,V1,W1,W1,MATURED,evaluation_E1_eligible
7-E2,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-08T12:05Z,99,2026-01-07T21:00Z,2026-01-08T12:00Z,SRC_A,V2,W1,W1,MATURED,evaluation_E2_revised_current
8,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-08T12:30Z,102,2026-01-07T21:00Z,2026-01-07T21:00:30Z,SRC_A,V1,W1,W2@2026-01-08T12:00Z,UNCHANGED,original_W1_score_only
9-C1,C1,2026-01-05T21:01Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,102,2026-01-07T21:00Z,2026-01-07T21:00:30Z,SRC_A,V1,W1,W1,MATURED,eligible_return_leg_only+partial_coverage
9-C2,C2,2026-01-05T21:02Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-08T21:00Z,2026-01-07T21:20Z,NONE_YET,,,,,V1,W1,W1,OPEN,window_open
9-C3,C3,2026-01-05T21:03Z,100,2026-01-05T21:00Z,2026-01-05T21:00:30Z,SRC_A,2026-01-07T21:00Z,2026-01-07T21:20Z,ABSENT,,,,,V1,W1,W1,MATURED-UNAVAILABLE,endpoint_missing
```

### Case 1 — Open window

- **Inputs:** Eval 2026-01-06T21:01Z. Horizon 2026-01-07T21:00Z not reached. Provisional mark: ASSET_X 101, observed 2026-01-06T21:00Z, known 21:00:30Z *(fixture completion)*. No admitted observation ≤ 98 so far.
- **Expected status/labels:** State `OPEN`. Mark labelled `PROVISIONAL — NOT SCORED`. Invalidation leg: `UNKNOWN` (coverage `PARTIAL` — window still running).
- **Score eligibility:** `INELIGIBLE — reason: window_open`. Excluded from matured and scored denominators; counted in `pending`.
- **Display:** Call view in full; provisional mark +1.0% with its observed-at — Class B provisional arithmetic under `NUM-CLASS-1`, rendered only with the `PROVISIONAL — NOT SCORED` label; state `OPEN`; time remaining to horizon.
- **Withhold:** Any win/loss/flat verdict; any contribution to accuracy; any unlabelled "+1%" figure; any Class A framing of the provisional figure.
- **FAIL example:** Accuracy tile on Jan 6 reads "C1 ▲ +1% — WIN" and the cohort accuracy denominator includes C1.

### Case 2 — Matured arithmetic control

- **Inputs:** Eval 2026-01-07T21:20Z (past horizon + `SYN-GRACE-10`). Endpoints ASSET_X 102, BENCH_Y 202, both observed 2026-01-07T21:00Z, known 21:00:30Z, single source, no conflict. No path observations supplied → invalidation coverage `UNKNOWN`. Rule under test: `SYN-RULE-1` exactly.
- **Expected status/labels:** State `MATURED`. Return leg: `CORRECT` — raw **+2.00%**, benchmark **+1.00%**, excess **+1.00pp**. Invalidation leg: `UNKNOWN`. No combined headline verdict (coverage unresolved; per contract 3.5).
- **Score eligibility:** `ELIGIBLE` for the return leg only, flagged `partial_coverage: invalidation_unknown`. Counted once in scored denominator for the return-leg statistic.
- **Display:** Both endpoints with source ID and clocks; the three return figures as separate lines; `Invalidation: UNKNOWN — no admitted path observations in fixture`; rule ID `SYN-RULE-1`.
- **Withhold:** A single unqualified "WIN" headline; excess presented as raw return; any claim that invalidation was checked and passed.
- **FAIL example:** Card shows "WIN +2%" with no benchmark line and no invalidation field — or shows excess as "+2.00pp".

### Case 3 — Missing endpoint / publication lag

- **Inputs:** Evals at 2026-01-07T21:01Z, 2026-01-07T21:10:00Z (subcase 3b, grace boundary), 2026-01-07T21:10:01Z (subcase 3c), and 2026-01-07T21:20Z. ASSET_X horizon endpoint absent at all evals. Grace policy: `SYN-GRACE-10` (10 minutes; grace window is the interval (21:00Z, 21:10:00Z]). Last admitted observation: baseline 100 @ 2026-01-05T21:00Z.
- **Expected status/labels:** At 21:01Z — `PENDING-PUBLICATION` ("awaiting endpoint publication, grace until 21:10:00Z"). **Boundary subcase 3b — eval exactly 2026-01-07T21:10:00Z: still `PENDING-PUBLICATION`** (the boundary instant is the last instant of grace; equality stays pending). **Subcase 3c — eval 2026-01-07T21:10:01Z, and the 21:20Z eval: `MATURED-UNAVAILABLE`** (first instant strictly after the boundary transitions). Invalidation leg `UNKNOWN` at all evals.
- **Score eligibility:** `INELIGIBLE — reason: endpoint_missing` at all evals. Counted in `missing` after grace; in `pending` through the boundary instant. If the endpoint arrives later, the record becomes a `revised` evaluation — it is never retro-labelled a failure.
- **Display:** State label; last known observation with its observed-at and age; grace deadline while pending.
- **Withhold:** Any numeric return of any class (`NUM-CLASS-1` — no observation exists to compute one from); 0%; "flat"; "loss"; any invented endpoint price.
- **FAIL example:** At 21:20Z the row renders "0.0% — FLAT" or "LOSS", or the call is removed from all cohort counts.

### Case 4 — Contradictory sources

- **Inputs:** Eval 2026-01-07T21:20Z. Provider A: ASSET_X 102, observed 2026-01-07T21:00Z, known 21:00:30Z. Provider B: ASSET_X 98, same clocks. Both current, equally available. **Missing policy:** no source-resolution/vintage policy is supplied in the seed. Synthetic assumption applied: `SYN-SRC-1`.
- **Expected status/labels:** State `CONFLICT`. Candidate outcomes shown as an unresolved pair: A → raw +2.00%; B → raw −2.00% (benchmark leg not computable until resolution; excess withheld). Invalidation leg `UNKNOWN` — neither value is *admitted*, and B's 98 sits at the horizon close, not an admitted in-window path observation.
- **Score eligibility:** `INELIGIBLE — reason: source_conflict`. Counted in `conflicting`, excluded from scored denominator.
- **Display:** Both values with provider IDs, observed-at, first-known-at; the literal label `UNRESOLVED — NO SOURCE POLICY DECLARED`; both candidate returns, each tagged with its provider — Class C candidate arithmetic under `NUM-CLASS-1`, each rendered with the `UNRESOLVED CANDIDATE — NOT SCORED` label.
- **Withhold:** Any single chosen endpoint; any averaged endpoint (100); any verdict; any excess figure; any candidate figure without its Class C label.
- **FAIL example:** UI adopts A's 102 and renders "+2% WIN" (cherry-pick), or averages to 100 and renders "0% FLAT".

### Case 5 — Stale observation

- **Inputs:** Eval 2026-01-07T21:20Z. Only candidate price: ASSET_X 102, **fetched** 2026-01-07T21:05Z, **observed** 2026-01-06T21:00Z (Jan 6 close). No observation exists at the 2026-01-07T21:00Z horizon close.
- **Expected status/labels:** State `STALE-ONLY` at horizon; after grace, `MATURED-UNAVAILABLE (stale-only)`. The 102 is displayed as "last observation 102 @ 2026-01-06T21:00Z — age 24h at horizon". Invalidation leg: `UNKNOWN`, coverage `PARTIAL` (one admitted path point, 102 > 98, no breach observed, coverage incomplete).
- **Score eligibility:** `INELIGIBLE — reason: endpoint_missing (stale_only)`. Counted in `missing`.
- **Display:** Last observation with observed-at primary and fetch time explicitly labelled `fetched`; staleness age; state label.
- **Withhold:** 102 in the endpoint field; any return computed from it; fetch time presented as observation time.
- **FAIL example:** Endpoint field shows 102 with timestamp "2026-01-07 21:05" and the card renders "+2% WIN".

### Case 6 — Known invalidation

- **Inputs:** Eval 2026-01-07T21:20Z. Admitted path observation: ASSET_X 97, observed 2026-01-06T21:00Z, known 21:00:30Z (97 ≤ 98, inside window → breach). Horizon endpoints: ASSET_X 102, BENCH_Y 202 *(benchmark is a fixture completion)*, observed 2026-01-07T21:00Z, known 21:00:30Z.
- **Expected status/labels:** State `MATURED`. Invalidation leg: `BREACHED @ 2026-01-06T21:00Z (97 ≤ 98)` — permanent on the call record. Return leg: `CORRECT` — raw **+2.00%**, benchmark **+1.00%**, excess **+1.00pp**. Headline (per controller clarification, §4 Q1): there is **no single headline** — the two legs are the headline, both rendered in headline position: `INVALIDATION: BREACHED` + `RETURN: CORRECT (+2.00% / +1.00pp)`. Neither leg governs, neither is hidden.
- **Score eligibility:** `ELIGIBLE`, counted **once** in the scored denominator, classified per the declared rule version (`SYN-RULE-1`) with the two-leg headline per §4 Q1.
- **Display:** Original invalidation rule verbatim; breaching observation with value and clocks; both legs side by side; rule IDs.
- **Withhold:** A lone "WIN +2%" (breach erased); a lone "INVALIDATED — LOSS" (return leg erased); any merged single number.
- **FAIL example:** Card renders only "+2% — WIN", with the Jan 6 breach nowhere on the call page.

### Case 7 — Corrected data

- **Inputs:** Initial endpoint ASSET_X 102, observed 2026-01-07T21:00Z, known 21:00:30Z, vintage `V1`. Initial evaluation `E1` at 2026-01-07T21:20Z under `SYN-RULE-1`: raw +2.00%, excess +1.00pp (benchmark 202, +1.00%, unchanged throughout). Correction: endpoint revised to **99**, first known **2026-01-08T12:00Z**, vintage `V2`.
- **Expected status/labels:** `E1` remains immutable and reachable, labelled `SUPERSEDED`. New evaluation `E2` evaluated_at 2026-01-08T12:05Z (≥ V2 first-known 2026-01-08T12:00Z), labelled `REVISED — data correction V2, first known 2026-01-08T12:00Z`: raw **−1.00%**, excess **−2.00pp**, with the delta vs E1 stated explicitly (+2.00% → −1.00%; +1.00pp → −2.00pp). Call counted once in `revised`, not double-counted in scored.
- **Score eligibility:** E1 was eligible when produced; E2 is the current evaluation. Any aggregate must declare which vintage it uses; mixing E1 and E2 across a cohort is prohibited.
- **Display:** Both vintages with their first-known clocks; what changed (endpoint 102 → 99), when it became known (Jan 8 12:00Z), and both score lines.
- **Withhold:** Any backdating of V2 knowledge to Jan 7; any silent overwrite of E1; any presentation of E2 as "the original result".
- **FAIL example:** History now shows "−1%" for C1 with no trace of E1, or the correction is timestamped as known 2026-01-07.

### Case 8 — Learned-weight change

- **Inputs:** C1 issued under weights `W1` (pinned on the call, with W1's learned-from vintage). Weights `W2` learned_at **2026-01-08T12:00Z**, learned from data through 2026-01-07T21:00Z. **Evaluation clock for this case is fixed at 2026-01-08T12:30Z.** Current product surfaces elsewhere use W2.
- **Expected status/labels:** C1's original-call view shows `weights: W1` permanently. Any current-weights display is a separate role labelled `current learned weights: W2 (learned_at 2026-01-08T12:00Z)` and must not appear inside C1's original evidence or scoring explanation except as that separate label. A W2 rescoring of C1, if offered, is labelled `COUNTERFACTUAL — NOT THE ORIGINAL SCORE`.
- **Score eligibility:** C1's original score (if any) remains the W1 score under its rule version. W2 produces no retroactive eligibility or verdict change.
- **Display:** Both weight versions with roles and learned-from vintages; C1 evidence list containing only items with available-at ≤ 2026-01-05T21:01Z.
- **Withhold:** W2 anywhere in C1's "known at issue" panel; any post-issue outcome/label in the original evidence list; any silent re-score.
- **FAIL example:** C1's detail page header reads "weights: W2", or its evidence panel includes a Jan 8 item.

### Case 9 — Zero / partial sample

- **Inputs:** Cohort of 3 calls, eval at **2026-01-07T21:20Z exactly**: `C1` = Case 2 control (matured, eligible, scored — return leg only, flagged partial coverage); `C2` (horizon **2026-01-08T21:00Z**; issued 2026-01-05T21:02Z; baseline 100, SRC_A — still inside its window at eval → `OPEN`); `C3` (issued 2026-01-05T21:03Z; horizon 2026-01-07T21:00Z; endpoint absent past grace → `MATURED-UNAVAILABLE`). Full fixed inputs per call are in the §(c) fixture table (rows 9-C1/9-C2/9-C3).
- **Expected status/labels:** Counts displayed exactly: **issued 3 · matured 2 · eligible/scored 1 · pending 1 · missing 1 · conflicting 0 · revised 0**. **Metric-specific denominators:** the return-leg scored denominator = **1** (C1 only), shown adjacent to any return-leg figure; the invalidation leg has **no accuracy denominator** in this cohort — it is reported only as coverage counts (established for 0 of 2 matured calls: C1 `UNKNOWN`, C3 `UNKNOWN`), never merged into the return-leg statistic. Headline rate: **suppressed** — display reads "1 of 1 scored calls correct on the return leg — sample too small, no accuracy rate claimed" (production minimum-n is unbound — `POLICY_UNCONFIGURED`, §4 gate B3; suppression is the fixture behaviour).
- **Score eligibility:** Only C1 contributes to any scored statistic. A parallel cohort with **zero** eligible calls must render its aggregate as `UNAVAILABLE` — never 0% and never 100%.
- **Display:** All seven counts; the denominator; the coverage statement; per-call states for C1/C2/C3.
- **Withhold:** Any headline percentage; any rate over the issued denominator (e.g. "33%"); any disappearance of the pending or missing call from the counts.
- **FAIL example:** Header reads "Accuracy: 100%" (from 1/1), or "Accuracy: 33%" (dividing by issued), or "Accuracy: 0%" for an empty cohort.

---

## (d) Clarifications — RESOLVED 2026-10-26 (controller, PR #2 comment `6410046097`)

**Q1 — Governing leg: RESOLVED.** For this contract and its synthetic cases, invalidation and terminal return are retained as **two explicit headline legs**. Disagreement is never collapsed into one win/loss, the favourable leg is never chosen, and neither leg is hidden. Contract 3.5 and Case 6 are updated to this expectation, and `SYN-INV-1` is retired. The controller states this is presentation guidance for the bounded proposal, **not** adoption of a production scoring policy — no production headline rule is claimed anywhere in this document.

**Q2 — Production policy values: RESOLVED as unconfigured.** Production source-resolution policy, publication grace, and minimum-n values **have not been verified and must not be invented**. Accordingly:

- Any production behaviour depending on one of those values is marked **`POLICY_UNCONFIGURED`**.
- Production headline rates and score-eligibility claims that require an unbound value are **withheld** — they are not computed from fixture values.
- The `SYN-*` assumptions above continue to provide deterministic synthetic coverage only. They are fixtures, **not product defaults**, and must never be presented as such.

**Production bindings still required — separate acceptance gate (does not block this synthetic deliverable):**

| Gate | Binding required | Fixture stand-in (not a default) | Behaviour until bound |
|---|---|---|---|
| B1 | Source-resolution / vintage policy for admitted-provider conflicts | `SYN-SRC-1` (conflict blocks scoring) | `POLICY_UNCONFIGURED`; no production score from a conflicted endpoint |
| B2 | Publication-grace duration per asset class | `SYN-GRACE-10` (10 minutes) | `POLICY_UNCONFIGURED`; no production maturity transition on grace expiry |
| B3 | Minimum scored-n for headline rates | Suppression at n = 1 (Case 9) | `POLICY_UNCONFIGURED`; production headline rates withheld |

Each binding, once declared with a policy ID/version, replaces its fixture stand-in without changing any case structure.

---

## Conformance assertions (falsifiable checklist)

An implementation conforms only if all of the following hold under the §0 fixture:

1. At eval 2026-01-06T21:01Z, no surface in the product shows a verdict, a win/loss label, or an accuracy contribution for C1.
2. No surface ever renders a **Class A (admitted/scored) return or any scored metric** for a call lacking an admitted horizon endpoint (Cases 3, 4, 5). Class B/C arithmetic, where it exists (Cases 1, 4), renders only under its `NUM-CLASS-1` label and enters no accuracy figure, rate, or denominator; in Cases 3 and 5 no arithmetic of any class appears.
3. In Case 4, both provider values and both candidate returns are reachable in ≤ the same number of clicks as any single-source verdict elsewhere; neither is pre-selected.
4. In Case 5, the endpoint field is empty/unavailable while the Jan 6 observation is displayed with observed-at 2026-01-06T21:00Z and a staleness age.
5. In Case 6, the breach (97 @ 2026-01-06T21:00Z) and the +2.00%/+1.00pp return leg are visible on the same call surface without expanding a "history" or "audit" view.
6. In Case 7, evaluation E1 is retrievable byte-identical after V2 arrives, and E2 displays "first known 2026-01-08T12:00Z" adjacent to the revised figures.
7. In Case 8, C1's original view contains no occurrence of `W2` outside a clearly separated "current weights" label, and no evidence item with available-at after 2026-01-05T21:01Z.
8. In Case 9, the strings "100%", "33%", and "0%" do not appear as cohort accuracy for the 3-call cohort or for an empty cohort; the counts 3/2/1/1/1/0/0 do appear.
9. Every displayed rate anywhere is immediately adjacent to its denominator and the seven cohort counts (or a link of ≤1 click to them).
10. Every displayed price shows observed-at; fetch time, if shown, is labelled as fetch time.
11. An index close is never rendered with an ETF/fill label, and the instrument-convention field (contract 3.4) is non-empty for every scored call.
12. Deleting or expiring source data changes no historical evaluation: E1-class records render identically from their pinned inputs.
13. No surface renders a single collapsed win/loss headline for a scored call: wherever both legs exist, the invalidation leg and the return leg both appear in headline position (Case 6 shape), and neither is reachable only via expansion or history.
14. On any production surface where gate B1, B2, or B3 is unbound, the dependent behaviour displays `POLICY_UNCONFIGURED` and no headline rate or score-eligibility claim requiring that value is rendered; no `SYN-*` fixture value (10-minute grace, conflict-blocks-scoring, n = 1 suppression) appears as, or is indistinguishable from, a product default.

---

*End of response. ACK and critique delivered as one document, per task terms; Amendment 1 incorporated 2026-10-26 per controller comment `6410046097`; Amendment 2 (R1) incorporated 2026-10-26 per the independent review at `ac3d33c48a`. No GRID source was read, no production data was used, and no GitHub publication is made by this document itself — the parent route posts it.*
