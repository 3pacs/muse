# ADOPT-C06 — storage-error visibility

**Status: DELIVERED 2026-10-18, awaiting verification.** Base: the
verified/closed ADOPT-C1-R1 pin `3ed17869`. Scope: exactly the
reproduced insert-failure path and its visibility/recovery. C07
corrupt-newest fallback recovery, conflict presentation beyond the
C1-R1 policy, and any broader exception redesign are NOT in scope
and are untouched.

## 1. The defect (as staged)

`maybePersistSnapshot` caught every insert error and treated it as
an assumed uniqueness race, returning nothing. A real storage
failure (the staged witness injects a non-unique `SQLITE_FULL`
rejection) therefore produced `ok: true` with no persistence field
at all: the live feed was truthful, but the saved trail silently
missed a valid observation until that frame happened to be
redelivered. The fix makes saving health explicit without ever
relabeling feed health.

## 2. What changed

**`server/src/actions.ts` (`674bc2969930…`)**

- The `getLive` response schema gains a required `persistence`
  object — the declared schema/type path, not an adapter-side
  extra:
  - `outcome`: `saved` | `already-saved` | `throttled` |
    `no-attempt` | `failed`
  - `reason`: `storage-full` | `storage-busy` | `storage-read-only`
    | `storage-unavailable` | `null` — a safe category only. The
    driver error is read internally to classify; its message, SQL,
    paths and any embedded details never reach the response.
- `maybePersistSnapshot` now returns that outcome:
  - unkeyed payload → `no-attempt` (unreachable post-normalize,
    stated rather than hidden);
  - instant already stored → `already-saved` (the C1-R1 dedupe);
  - inside the 45-second gap → `throttled`;
  - insert lands → `saved`. The benign overlap needs no exception:
    migration 0003's trigger ignores a duplicate-instant insert
    inside the statement and the driver reports **zero rows
    affected**, which is read as `already-saved`. An insert (or
    admission-check, or prune) error is **`failed`** with the
    classified category — no error is presumed to be a race anymore.
    A prune failure reports `failed` for the step as a whole (the
    admitted frame's own row is stored and redelivery dedupes, so
    nothing is corrupted or duplicated by that report).
- The feed-error branch returns `persistence: { outcome:
  "no-attempt", reason: null }` — no frame arrived, nothing is
  dressed up as a saving success. Feed status semantics are
  otherwise byte-identical: a valid feed with a failed save still
  returns `ok: true` and the live payload.

**`client/src/App.tsx` (`e5dfc336f14d…`)** — the Trail panel shows,
only when the latest response's outcome is `failed`, one line
beside the trail: “Saved trail unavailable — snapshots aren’t
being stored right now (storage full|busy|read-only). The live
feed is unaffected.” It renders purely from the latest response,
so a later healthy response clears it on the next poll; no new
polling or state machinery was added.

**Offline harness support** — `offline/preview.ts` gains an
`OFFLINE_INSERT_FAIL=1` fake-insert fault (coded `SQLITE_FULL`),
and `offline/offline-build.mjs` gains a `storage-warning` preview
case plus a healthy-case exclusion assertion (below).

Nothing else changed: schema.ts, both migrations, the C1-R1
trigger, retention/dedupe/throttle arithmetic, normalization and
the signals path are byte-identical to the closed pin.

## 3. Evidence

**Fault/recovery harness (new)** — `offline/snapshot-audit-c06.mjs`
+ `offline/snapshot-audit-c06-entry.ts`, committed receipt
`offline/snapshot-audit-c06-receipt.json` (`71a7eaee6c73…`). It
runs the REAL C06 `getLive` handler + real schema + verbatim
0002/0003 DDL on drizzle-orm 0.45.2 / @libsql/client 0.14.0
in-memory storage, with fault injection by a TEST-ONLY trigger
(`RAISE(ABORT)` on insert, disposable storage only — no real disk
is filled, no production storage touched). **5/5 PASS**:

- **S01** failure with no prior rows: `ok: true`, live frame
  present, `persistence = failed / storage-unavailable`, 0 rows,
  empty trail — no saved observation is claimed.
- **S02** the staged witness, corrected: first frame `saved`;
  under fault, the new frame's response keeps `ok: true` and shows
  the new live frame, `persistence = failed`, stored rows stay 1,
  trail stays at the first frame.
- **S03** recovery: fault dropped, the same frame redelivers and
  saves exactly once under its original identity (rows 2, trail
  catches up, outcome `saved` — the UI warning therefore clears);
  an exact replay is `already-saved`, no duplicate.
- **S04** benign outcomes never report failure: a +30s frame is
  `throttled`; the overlapping equivalent-instant pair resolves to
  `saved` + `already-saved` with exactly 1 row (the rows-affected
  signal, not an exception).
- **S05** feed-down carries `persistence = no-attempt`, reason
  null.

The injected abort exercises the classifier's default branch
(`storage-unavailable`); the full/busy/read-only categories map
from driver error codes through the same single classification
function.

**Preserved properties** — the C1-R1 harness re-run against this
revision: **14/14 PASS** (identity, retention, migration parity
battery, unkeyed exclusion, atomic admission all unchanged).

**Schema/UI proof (SSR preview layer)** — the offline build's new
`storage-warning` preview runs the real handler with the injected
insert fault and server-renders the real App: the retained
`preview/storage-warning.html` shows **LIVE** alongside “Saved
trail unavailable … (storage full)”, with payload assertions
(`getLive.persistence.outcome = failed`, `reason = storage-full`)
enforced by the build itself. The healthy `success` preview
asserts the warning's absence (and `persistence.outcome = saved`).
Clearing on recovery is proven at handler level by S03 plus the
render rule (warning iff the latest response says `failed`).
Layer statement: this is the SSR preview layer that has carried
view-state evidence since ADOPT-B1-R1; no new browser case was
added for the warning.

**Preserved lanes** — SSR: preflight 13/13, boundary 51/51, all
nine retained preview HTMLs byte-identical; payload JSONs change
only by the added `persistence` field; BUILD-MANIFEST refreshed
(33 inputs — actions/App/preview/offline-build hashes; 46 outputs
with the new case). Browser lane: all 9 cases pass with fresh
reports; the case HTML changes only by the `persistence` field in
the embedded response JSON (visible DOM identical); fresh HTML +
responses adopted as the retained packet, screenshot entries
bound to the retained PNGs (the warning does not render in those
cases), outputs verify, inputs 38 → 41 (the C06 harness files
enter the scan). Backend unchanged: compile 12/12, J1 50/50 +
27/27 + 27/27, watcher 0 failures.

## 4. Scope limits (unchanged honesty labels)

Hosted platform DB behavior remains UNRUN, as before. The two
omitted browser bundles remain UNAVAILABLE. The outcome describes
the persistence attempt of the response that carries it; it is
not a storage health history and makes no claim about attempts
made by other polls or processes.
