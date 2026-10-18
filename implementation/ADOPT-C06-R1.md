# ADOPT-C06-R1 — accurate post-insert maintenance warning

**Status: DELIVERED 2026-10-18, awaiting verification.** Base: the
verified ADOPT-C06 pin `a034ec1e`. Scope: exactly the one reproduced
warning-accuracy defect from the C06 verification (PR #2 head
`bb5e2f4c`). No status/API redesign, no new polling, no DB change;
C07 stays deferred and untouched.

## 1. The defect (as reproduced by the reviewer)

C06 catches a prune-query failure after the insert commits and
reports `failed / storage-busy` for the persistence step as a whole —
a valid maintenance diagnostic. But the App's unconditional
failed-outcome text said **"Saved trail unavailable — snapshots
aren't being stored right now."** Under a one-shot prune SELECT
failure, the current frame IS stored (2 rows) and IS in the returned
trail, so both claims were false for that fault. The insert-failure
case the text was written for is only one of the two ways the
`failed` outcome arises.

## 2. What changed

**`client/src/App.tsx` (`e26fc9ddc26d…`) — the only product-source
change.** The failed-outcome warning now describes the whole
persistence step, in the neutral form the brief accepts:

> "Snapshot saving problem — the latest saving step didn't finish
> (storage full | busy | read-only | unavailable). The live feed is
> unaffected."

That sentence is true for an insert failure (the step did not
finish; nothing was saved) and for a post-insert maintenance
failure (the step did not finish; the frame may already be
stored). It claims nothing about whether the current frame was
saved and nothing about trail availability. The warning still
renders only from the latest response's outcome, still shows only
the safe category, and still clears on the next healthy response.
The `storage-unavailable` category now also gets its parenthetical
label (previously unlabelled).

**Nothing else in product source changed.** `server/src/actions.ts`
is byte-identical to the verified C06 pin (`674bc2969930…`) — the
typed outcome, whole-step `failed` reporting for prune errors, safe
classification, feed semantics, schema and both migrations are
exactly as verified. The documented admission-versus-retention
semantics of `saved` are unchanged, per the brief.

## 3. Evidence

**Finite harness (extended)** — `offline/snapshot-audit-c06.mjs` +
`offline/snapshot-audit-c06-entry.ts`, committed receipt
`offline/snapshot-audit-c06-receipt.json` (`d905b8515dcf…`):
**6/6 PASS**. S01–S05 re-run unchanged and passing (insert failure
on empty storage; failure with last-good trail; same-frame
recovery; benign throttle/overlap; feed-down no-attempt). New:

- **S06 — post-insert prune failure.** The insert commits; a
  one-shot failure of the prune-enumeration SELECT then makes the
  step report `failed / storage-busy`. Asserted together: `ok:
  true` with the live frame, 2 stored rows **including the current
  frame**, the returned trail **includes the current frame**, and
  the App's failed-outcome warning is the corrected whole-step
  text (the source contains neither "being stored right now" nor
  "Saved trail unavailable"). Fault-injection honesty: a SQL
  trigger cannot fail a later SELECT, so this one fault is injected
  at the db facade — the wrapped db counts selects and the third
  select of the call (same-instant check, latest check, prune
  enumeration) rejects once with a `SQLITE_BUSY`-coded error; every
  other statement runs on the real drizzle/libsql stack and the
  rows/trail are read back from real storage. The substitution is
  disclosed in the entry header and the receipt mode line (the
  reviewer's own proof used the same facade technique).

**SSR/text fixture (the existing preview layer)** —
`offline/preview.ts` gains `OFFLINE_PRUNE_FAIL=1` (the fake insert
commits; the third select of the call rejects once, coded
`SQLITE_BUSY`), and `offline/offline-build.mjs` gains a
`storage-maintenance` preview case. The retained
`preview/storage-maintenance.html` renders **LIVE** beside the
corrected warning ("…didn't finish (storage busy)"), and its
payload asserts `persistence = failed / storage-busy` with the
frame present in `trail` (length 1, spot 500.25) — the stored/
trail result and the corrected warning asserted together at this
layer. Controls kept: the ordinary insert-failure case
(`storage-warning`, retained HTML changed by exactly the warning
sentence) still renders the warning with its safe category, and
the healthy `success` case asserts the warning's absence (it now
excludes both the new and the retired wording). Layer statement:
this is the SSR preview layer that has carried view-state evidence
since ADOPT-B1-R1; no new browser case was added for the warning.

**Preserved lanes** — C1-R1 harness re-run at this revision:
**14/14 PASS** (its committed receipt stays bound to the closed
C1-R1 pin; the 53-case migration parity evidence is untouched —
no migration or actions.ts byte changed). SSR: preflight 13/13,
boundary 51/51, tsc clean; the nine other retained preview HTMLs
and all payloads are byte-identical to the C06 pin except the
`storage-warning` sentence above; BUILD-MANIFEST refreshed (33
inputs — App/preview/offline-build hashes changed; 50 outputs with
the new case). Browser lane: 9/9 cases + 7/7 controls pass with
fresh reports, failures none; case HTML and responses are
byte-identical to the C06 pin (only the hash-recorded
`assets/app.js` output changed — the bundle is not committed);
screenshot entries rebound to the retained PNGs; 38/38 available
outputs verify with 0 cross-section conflicts; inputs 41 (6
changed: App, preview, offline-build, the C06 harness pair and its
receipt). Backend unchanged: compile 12/12, J1 50/50 + 27/27,
watcher 0 failures.

## 4. Scope limits (unchanged honesty labels)

Hosted platform DB behavior remains UNRUN, as before. The two
omitted bundles (client/server build outputs and the browser
`assets/app.js`) remain hash-recorded / UNAVAILABLE as files. The
`persistence` outcome still describes the persistence step of the
response that carries it; `saved` remains an admission
acknowledgment, not a retention guarantee.
