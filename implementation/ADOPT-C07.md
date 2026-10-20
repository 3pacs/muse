# ADOPT-C07 — bounded last-good fallback recovery

**Status: DELIVERED 2026-10-20, awaiting verification.** Base: the
verified ADOPT-C06-R1 pin `c3cf7897`. Scope: exactly the fallback
selection/diagnostic path named in the PR #2 task "ADOPT-C07 bounded
last-good fallback recovery" and its finite acceptance table. No
persistence, trail, retention, migration or parity change; C06
semantics and the closed C1-R1/F1 behavior are intact. A
post-delivery **coherence revision** (raw stored timestamp must
also name the chosen row's keyed instant) is recorded in section
5; the current source includes it.

## 1. The defect (as reproduced by the reviewer)

In `loadTrailAndLatest` (`server/src/actions.ts`), the feed-down
fallback considered ONLY the single newest keyed row. If its
`payload_json` failed `JSON.parse` or `normalize()` returned null,
`staleSnapshot` was null **but** `staleSnapshotAt` was still set to
that corrupt row's `updatedAt` — an older usable stored frame was
suppressed, and a timestamp was advertised beside a null payload
with no reason. The reviewer's witness: frames 23:30 (spot 500)
and 23:31 (spot 501) stored, the 23:31 payload corrupted, feed
down → `staleSnapshot: null`, `staleSnapshotAt: 23:31`, trail 2.

## 2. What changed

**`server/src/actions.ts` (`80b232a1f256…`) — fallback selection
and the response schema only.**

- The single-row newest query is replaced by a **bounded candidate
  scan**: keyed rows only (`instantMs NOT NULL`, per C1-R1),
  ordered `(instantMs DESC, id DESC)`, `LIMIT 240` — the existing
  trail bound, reused as the finite candidate bound.
- A candidate is **usable** only when (a) its stored payload parses
  as JSON, (b) the existing F1 `normalize()` admits it, unchanged,
  and (c) **coherence**: the normalized payload's own clock
  (`updated_at`) is the same canonical instant as the row's keyed
  `instantMs`. Instants are compared as parsed epoch milliseconds,
  never as strings, so equivalent aware spellings of one instant
  (`Z` vs `+02:00`) agree, while a payload whose clock names a
  different instant is skipped — never guessed, repaired, merged
  or rewritten. The first usable candidate wins.
- `staleSnapshot` / `staleSnapshotAt` come from the **chosen row
  only** (its raw stored payload and its raw stored timestamp
  spelling). If no candidate in the window is usable, **both are
  null** — a timestamp is never again advertised beside a null
  payload.
- One new safe diagnostic field in the `getLiveResponse` schema:
  **`staleSnapshotReason`** — a nullable enum, null on a live
  (`ok: true`) response:
  - `"current"` — the newest keyed row was usable and selected;
  - `"earlier-usable"` — one or more newer candidates were skipped
    and an older usable stored frame was selected;
  - `"empty-storage"` — no keyed candidate rows exist at all;
  - `"no-usable-candidate"` — candidates were examined, none was
    usable, and the window was not exhausted;
  - `"window-exhausted"` — the full 240-candidate bound was
    examined with none usable. This claims only that no usable
    fallback was found **in the examined window**, never that all
    historical storage is invalid.
  No raw JSON, SQL, paths or exception text appear anywhere in the
  field. `feedError` remains about the feed only.
- **Unchanged, deliberately:** `maybePersistSnapshot` (C06
  persistence semantics byte-identical in behavior), `normalize`,
  the trail query and its behavior, `schema.ts`, both migrations,
  retention, and ordering.

**`client/src/App.tsx` (`2203fbd2dd45…`) — text/conditional only.**
In the feed-down stale banner, when `staleSnapshotReason` is
`"earlier-usable"` the banner adds one plain sentence beside the
stale time: **"Showing an earlier usable saved frame."** When both
fallback fields are null, no saved frame or time is advertised
(unchanged: no display frame, no banner). The fallback still
renders **FEED DOWN**, never LIVE/fresh, and the C06 warning text
is untouched.

## 3. Evidence

**Finite harness (new)** — `offline/snapshot-audit-c07.mjs`
(`09a06ef84d6d…`) + `offline/snapshot-audit-c07-entry.ts`
(`a49c2994173d…`), committed receipt
`offline/snapshot-audit-c07-receipt.json` (`26b45ab5d984…`):
**11/11 PASS**. The REAL `getLive` handler + REAL schema + verbatim
0002/0003 DDL on drizzle-orm/libsql (in-memory, disposable); the
only substitutions are the lane's SDK adapter and an in-memory
fetch stub. Cases seed stored rows directly in disposable storage
where the required state is one the live path would never produce
(corrupt payload bytes, identity mismatch, >240 rows) — disclosed
in the entry header; the code under test never writes those rows.

| Case | Result |
| --- | --- |
| T01 newest usable → selected unchanged, coherent pair, reason `current` | PASS |
| T02 newest corrupt JSON + older usable → older payload with ITS timestamp, reason `earlier-usable`, both stored rows byte-unchanged | PASS |
| T03 newest parses but fails admission (naive payload clock) → skipped, next usable selected | PASS |
| T04 payload identity mismatch (payload clock ≠ row instant) → skipped, next usable selected | PASS |
| T05 equivalent aware spelling (`+02:00` row, `Z` payload, same instant) → usable, `staleSnapshotAt` is the row's raw spelling | PASS |
| T06 empty storage → both null, reason `empty-storage` | PASS |
| T07 all candidates unusable (3 < bound) → both null, reason `no-usable-candidate` | PASS |
| T08 245 rows, first 240 in scan order corrupt, usable row beyond the bound → both null, reason `window-exhausted`; the beyond-bound usable row was NOT returned (the scan stayed bounded) and all 245 rows remain stored | PASS |
| T09 the reviewer's witness exactly (23:30 spot 500 / 23:31 spot 501, 23:31 payload corrupt, feed down) → the 23:30 frame, `staleSnapshotAt` 23:30, reason `earlier-usable`, `ok: false` | PASS |
| T10 live response → reason and both fallback fields null, persistence `saved` | PASS |
| T11 App binding: the earlier-usable note renders from `staleSnapshotReason` beside the stale banner; C06 warning text intact | PASS |

**C06-R1 regression (acceptance j)** — the prior harness re-run
unchanged at this revision: **6/6 PASS**, including S06, the former
post-insert maintenance-failure case (valid live frame, persistence
`failed / storage-busy`, current frame stored and in trail). Its
committed receipt stays bound to the closed C06-R1 pin, as in
prior lanes. **C1-R1 harness re-run: 14/14 PASS.**

**SSR preview layer** — `offline/preview.ts` gains
`OFFLINE_FALLBACK_SEED=1` (seeds a corrupt newer saved row and a
usable older one in scan order) and `offline/offline-build.mjs`
gains an **`earlier-usable`** preview case: feed down, the REAL
handler returns the older frame (spot 499.5) with
`staleSnapshotAt` `2026-01-04T23:04:00+00:00` and reason
`earlier-usable`, and the REAL App renders **FEED DOWN** beside
"Showing an earlier usable saved frame." Retained
`preview/earlier-usable.html` / `.payload.json` carry this state.
All other retained preview HTMLs are byte-identical to the C06-R1
pin; every payload changes only by the new `staleSnapshotReason`
field (the retained `error` case now truthfully reports
`empty-storage` on empty fake storage). SSR BUILD-MANIFEST
refreshed: 36 inputs / 54 outputs.

**Browser lane** — re-run at this revision: **9/9 cases + 7/7
controls PASS, failures none**; aggregation counterexamples 14/14.
Case HTML/responses change only by the embedded
`staleSnapshotReason` field; fresh reports are bound in
`BROWSER-MANIFEST.json` (inputs 41 → 44 with the C07 harness
files); screenshot entries are rebound to the retained PNGs
(37/37 PNG references verify against the packaged bytes).

**Backend suites re-run unchanged:** boundary tests 51/51,
`tsc --noEmit` clean (client + server, inside the offline build),
compile 12/12, watcher 0 failures, J1 50/50 + 27/27.

## 4. Scope limits (unchanged honesty labels)

Hosted platform DB behavior remains UNRUN, as before. The two
omitted bundles (client/server build outputs and the browser
`assets/app.js`) remain hash-recorded / UNAVAILABLE as files. The
fallback scan qualifies only the payload used as fallback within
the examined 240-row window; it is not a certification or repair
of stored history, and it never modifies a stored row.

## 5. Coherence revision — raw stored timestamp (2026-10-20)

**Reviewer finding (independent check of the delivered source,**
docs `4d26722c`, "13/14 focused cases, delivery still pending"):
after two legitimate `getLive` saves at 23:30 (spot 500) and 23:31
(spot 501), alter **only** the newer stored row's raw `updated_at`
text to 23:32 in disposable storage. Its accepted `instant_ms` and
its payload clock remain 23:31. The delivered code compared the
payload clock only to `instant_ms`, selected that row as
`current`, and returned `staleSnapshotAt`
`"2026-10-16T23:32:00.000Z"` beside a payload whose own
`updatedAt` is 23:31 — an incoherent pair, while a coherent older
row (23:30) existed. Controlled metadata corruption in disposable
storage only; not evidence of deployed corruption.

**The fix** — `server/src/actions.ts` (`247b3ecaa8d8…`), the same
fallback candidate loop, one added check: a candidate is usable
only if its **raw stored `updated_at`** also parses — via the
existing `parseAwareInstant` — to the row's accepted canonical
`instantMs` (the same instant the payload clock must already
equal). If the raw text does not parse, or parses to a different
instant, the candidate is skipped — never repaired, guessed or
rewritten. `staleSnapshotAt` returns the raw text verbatim, so the
raw spelling is part of the advertised pair and must cohere.
Equivalent aware spellings still pass (T05's `+02:00` row spelling
parses to the same instant and remains usable). Nothing else
changed: `normalize`, persistence, the trail, `schema.ts`, the
migrations, and `client/src/App.tsx` (`2203fbd2dd45…`, untouched
by this revision) are all as delivered. If no coherent candidate
exists in the 240 bound, the existing null/reason results apply
unchanged.

**Evidence at this revision:**

- C07 harness extended — `offline/snapshot-audit-c07-entry.ts`
  (`b4948324ebc9…`), driver `offline/snapshot-audit-c07.mjs`
  (`a77516f5eceb…`), regenerated committed receipt
  `offline/snapshot-audit-c07-receipt.json` (`7a6b096cd7e9…`):
  **13/13 PASS**. New cases: **T12**, the reviewer's witness
  exactly (two saves through the REAL handler, then a direct
  storage UPDATE setting only the newer row's `updated_at` text
  to `"2026-10-16T23:32:00.000Z"`; feed down → the 23:30 payload,
  `staleSnapshotAt` = the 23:30 row's raw spelling, reason
  `earlier-usable`, `ok: false`, and both stored rows
  byte-unchanged afterwards — the altered 23:32 text stays as
  stored, unrepaired); **T13**, the newest row's raw `updated_at`
  unparseable (`"not-a-timestamp"`, payload clock and keyed
  instant in agreement) beside a coherent older row → newest
  skipped, older selected, `earlier-usable`. T01–T11 unchanged
  and still passing.
- **Regressions re-run at this revision:** C06-R1 harness **6/6
  PASS**; C1-R1 harness **14/14 PASS** (committed receipts stay
  bound to their closed pins, as in prior lanes).
- **SSR packet refreshed** (`preview/BUILD-MANIFEST.json`,
  `4c6d1ee74891…`): the offline build re-ran; **every retained
  preview HTML and payload is byte-identical** to the delivered
  packet (all preview seeds store coherent rows, so no case's
  content moves), and the client bundle outputs are identical.
  Only bindings moved: the four changed input entries
  (`server/src/actions.ts`, the C07 harness entry/driver/receipt)
  and the hash-recorded server bundle output
  (`server/actions.js`, 185,767 → 185,847 bytes).
- **Browser packet refreshed**
  (`browser-preview/BROWSER-MANIFEST.json`, `4383328d349b…`):
  lane re-run, **9/9 cases + 7/7 controls PASS, failures none**,
  aggregation counterexamples 14/14. Case HTML and responses are
  byte-identical to the delivered packet; screenshot entries are
  rebound to the retained packaged PNGs (**38/38 PNG references
  verify** against the packaged bytes). Residual manifest change
  beyond the four input bindings is fresh settle timings
  (`elapsedMs`) in the case/control reports only — no assertion,
  verdict or content change.
- **Package:** still **160 files / 158 hashed** (no files added
  or removed); `sha256sum -c` clean on the final tree.
