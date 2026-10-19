# STRESS-P1 — Validated Atomic Refresh Admission (C07–C10)

**Task:** STRESS-P1 from the user-authorized offline stress review of
2026-10-06 (PR #2 comment 6012967705; full evidence in
`docs/MUSE-REDTEAM-REVIEW-20261004.md` at `ce2ad067`). One prioritized
task: validated atomic refresh admission for the LIVE-G1 delivery page.

**Base:** `redteam/ui-g3` at `6ffff8ab6af60d90e624e3b1af333f6bbc2ca077`
(the stress-reviewed candidate). The local source tree was verified
blob-identical to that pin (16/16 present files; the two remaining tree
files, `live_g1_mapping.md` / `live_g1_timeline.md`, were fetched from the
pin unchanged). The baseline build reproduced the pinned receipt exactly
before any change: 23,747 bytes, sha256
`17e62caf939d79c1aa7aba243400b94922ad59e0a0df0843eb5fbd649c175ed6`.

## The defects (all reproduced locally before the fix)

Driving the actual public controller `LIVE_G1.refresh()` of the built page
in headless Chrome with a scripted transport, the unmodified candidate
failed exactly as the review documented (receipt:
`tests/stress-p1-baseline-results.json`, 8/24):

- **C07** — a newer snapshot with `history.records` an *object* was
  committed: metrics showed spot 900 while ranges still showed 800, the
  refresh promise rejected with `recs.slice is not a function`, and the
  corrupt history stayed in the globals. A valid retry at the same frame
  also threw — the premature commit had consumed the frame identity.
- **C08** — `snapshot.fields` as a string (then as an array) was admitted
  as a field map: metrics went unavailable, the badge said fresh, and the
  identity was consumed so the valid retry was treated as not-newer.
- **C09** — a snapshot asserting `adapter_version: unsupported/v99` was
  admitted and displayed under the page's declared v1 / `8649ad54`
  provenance with no label or rejection.
- **C10** — status `reachable=false` with `data_vintage.stale=false`
  rendered **disconnected and fresh simultaneously**.
- **R4 (included per the brief's same-lane allowance)** — the date-only
  clock `2026-10-07` satisfied `_hasExplicitZone` (its trailing `-07` day
  matched the offset alternative) and was admitted as a frame, poisoning
  the identity for every later valid frame that day.

## The change (template.html only, four edits)

1. **Staged tuple validation — `_validateTuple(status, snapshot, history)`**
   runs before any last-good state or DOM change:
   - `snapshot` must be a non-array object and `snapshot.fields` a
     non-array object (an actual field map; field *contents* are not
     re-validated — legitimate `null`/`unavailable` fields stay legal).
   - `history` must be a non-array object whose `records` is an array of
     non-array objects (the declared ADAPTER_SPEC shape).
   - `status` may be null (badges render unknown, as before); when present
     it must be a non-array object.
   - **Source-identity policy:** any payload asserting an
     `adapter_version` outside `['live-g1/v1']` or a `backend_pin` outside
     `['8649ad54']` rejects the tuple, as does a tuple whose payloads
     assert differing values. The supported sets are declared constants
     next to the check (with a comment in ADAPTER_SPEC terms): a future
     compatible release is supported by extending the declared sets in the
     delivery — the same mechanism by which the footer pin is maintained —
     not by silently relabeling foreign data as pinned v1. Payloads that
     assert neither field are not identity-checked.
2. **Atomic admission in `_doRefresh`:** the candidate tuple is validated
   as a unit together with the existing clock/newer checks. Rejection
   changes nothing — last-good globals, DOM, failure state and frame
   identity are untouched, and the note names the reason
   (`Invalid frame rejected (<reason>) — kept last good snapshot.`). A
   valid retry at the rejected candidate's timestamp is admitted normally.
3. **Badge honesty in `render`:** when `backend.interpreter.reachable`
   is false, the freshness badge is `stale: <vintage reason or 'backend
   unreachable'>` — never `fresh` — regardless of a contradictory
   `data_vintage.stale=false` (adapter honesty rule 1).
4. **R4 zone guard:** `_hasExplicitZone` now requires a time component
   (`[T ]HH:MM[:SS[.fff]]`) before the zone designator, so a calendar
   day cannot masquerade as an offset. Valid `Z` / `±HH:MM` / `±HHMM` /
   `±HH` clocks, equal-instant offset equality, and timezone-less
   rejection are preserved.
5. Defense in depth: the ranges renderer now guards
   `Array.isArray(records)` so `render()` cannot throw on that path even
   for out-of-band data. (Admission is the fix; this is a seatbelt.)

`READINESS.md` gained two surgical updates in the same candidate: the
STRESS-P1 admission bullet under Code-ready, and the standalone-HTML size
corrected to the candidate's exact 27,275 bytes (it previously said 19KB,
already stale at the base pin). Nothing else in it was touched.

## Verification

**New harness** (`tests/stress-harness.mjs`, results in
`tests/stress-p1-results.json`): drives the real built page in headless
Chrome via CDP, stubs transport at `window.fetch` (the page's only
transport seam — the same public-controller method class as the review
workloads), and asserts DOM text, badge state, note text, globals and
promise rejection across 24 cases: boot, base admission, C07 + same-frame
valid retry, C08 string/array + retry, four C09 variants + retry, C10,
transport-failure retention / equal-frame / newer-recovery (C06 class),
timezone-less + date-only rejection, equal/newer offset instants
(C11 class), 10-call burst coalescing to exactly one follow-up
(C01/C02 class), 20,000-record history with 12 visible rows (C12 class),
malformed-JSON retention, final recovery. **24/24 PASS** against the
rebuilt page. The same harness against the unmodified pin scores 8/24
with the failure signatures quoted above
(`tests/stress-p1-baseline-results.json`).

**Preserved lanes:**
- Exact build: baseline reproduced the pinned receipt byte-identically;
  post-change rebuilds are deterministic (identical sha256 across runs).
- Adapter suite (`test_adapter.py`, adapter code untouched, byte-identical
  to the pin): **31/31 PASS** against the live backend.
- Offline compatibility checks (`harness.py`): **10 passes, 0 failures**.
- HTTP wrapper (`delivery/serve_adapter.py`): untouched, byte-identical
  to the pin; the reviewer's wrapper suites exercise that file and the
  adapter CLI, neither of which this change modifies.
- The reviewer's own browser/adapter/wrapper suites (23/23, 22/22, 7/7 at
  the base pin) run in the reviewer's environment; locally, the behaviors
  they protect are covered by the harness mapping above plus the local
  adapter suite. `verify_r1.py` / `verify_r2.py` need a reviewer fixture
  (`/tmp/accepted_tape_db.py`) that no longer exists locally; they test
  the adapter, which is unchanged.

**Build identity after the change:** template sha256
`f1913f1bdced8196f54a313f45d2834a9275dac203f7edb36ff443b2f77dcd54`;
built HTML 27,275 bytes, sha256
`10120fd57af8d3fb6a7178840dda7ed23e78f81c3831ad2147e96943235dc6c6`
(`delivery/BUILD_RECEIPT.json` regenerated by `build.py`).

## Out of scope (per the brief)

- **C05** request deadline/cancellation: a separately recorded subsequent
  task; not a STRESS-P1 acceptance gate. No deadline was invented here.
- No estimator, provider, credential, hosted-traffic, merge/deployment or
  trading changes. Captures were not regenerated; the embedded data and
  its provenance are unchanged.
