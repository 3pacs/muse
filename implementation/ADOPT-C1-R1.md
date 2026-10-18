# ADOPT-C1-R1 — chronological snapshot identity, ordering and retention fix

Base: the accepted ADOPT-C1 audit pin `2eb8159deac1061da12af58540c14757be11bbf5`.
This completion fixes the shared source-time contract behind the C03 and
C08 counterexamples. C05 (beyond the storage policy in §3), C06 and C07
are deferred per the brief and are NOT changed here: the insert catch-all
and the corrupt-newest fallback behavior are byte-for-byte the audited
ones. No other application behavior changes: F1 admission/zero/null
semantics, the 45-second gap rule, the 240-point trail and every
response field keep their shapes.

## 1. The fix (three files)

**`server/src/schema.ts`** (sha256 `35088a869346…`) — the `snapshots`
table gains `instantMs: integer("instant_ms")`, the validated UTC
instant (epoch milliseconds) of the frame. The table comment now states
the contract: `updated_at` text is preserved verbatim as provenance and
stays unique per stored spelling, but observation IDENTITY is the
instant. The column is nullable in the type because legacy rows whose
stored timestamp does not parse keep NULL (see §3).

**`drizzle/0003_snapshot_instant.sql`** (sha256 `b7056d1725eb…`) — the
additive migration: `ALTER TABLE … ADD COLUMN instant_ms`, a backfill
`UPDATE … SET instant_ms = CAST(ROUND(unixepoch(updated_at,'subsec')*1000)
AS INTEGER) WHERE instant_ms IS NULL AND unixepoch(updated_at) IS NOT
NULL`, and an index on `instant_ms`. The backfill expression was verified
against the packaged libsql build before adoption: offset spellings
(`2026-10-17T01:30:00+02:00`) and millisecond spellings
(`2026-10-16T23:30:00.250Z`) convert to the exact epoch millisecond. The
migration deletes, merges and rewrites NOTHING — `updated_at` and
`payload_json` keep their original bytes on every row.

**`server/src/actions.ts`** (sha256 `592c8c29652f…`) — the persistence
and load paths switch every comparison from the timestamp string to the
instant key:

- `maybePersistSnapshot` computes `instant = parseAwareInstant(
  payload.updatedAt)` (the F1-validated instant; null is unreachable
  post-normalize and persists nothing). Identity is now an existence
  check on `instant_ms`: any stored row for the instant — whatever
  spelling it was stored under, including a backfilled legacy row —
  dedupes the delivery. The throttle gap compares the candidate instant
  against the latest persisted instant (max `instant_ms`, id-desc
  tie-break), same 45s rule, same sign convention (negative gap = late
  arrival, still inserted). Inserts now write `instantMs` alongside the
  unchanged columns; the insert catch block is untouched.
- Retention now keeps exactly the newest `MAX_SNAPSHOTS` (1500)
  observations ordered by `(instant_ms DESC, id DESC)`: the row at the
  boundary defines a delete predicate for everything strictly below it
  (older instant, or same instant with lower id, or NULL instant against
  a real boundary; against a NULL boundary only the lower-id NULL tail).
  The C08 off-by-one (`id <= ids[len-1500]`, 1499 retained) is gone, and
  because the key is source time rather than arrival id, a late-arriving
  old frame can never evict a newer accepted observation — at capacity
  it is itself the row pruned.
- `loadTrailAndLatest` selects the trail (newest 240) and the newest row
  by `(instant_ms DESC, id DESC)`; the trail is reversed into ascending
  `(instant, id)` order. `staleSnapshotAt` and every trail point still
  report the row's ORIGINAL stored `updated_at` spelling — provenance
  is inspectable in the response exactly as stored.

Imports change accordingly (`asc`/`lte` dropped; `and`/`eq`/`isNotNull`/
`isNull`/`lt`/`or` added — `noUnusedLocals` typecheck passes via the
offline build).

## 2. Determinism and tie policy

- One instant = one observation for all NEW writes (first delivery
  wins; see §3 for differing payloads).
- Stored-row ties (possible only among pre-migration legacy rows that
  spell one instant two ways) resolve by row id everywhere: "newest" is
  the highest id at the greatest instant; trail order is `(instant,
  id)` ascending. No read path merges, rewrites or deletes them.
- Rows with `instant_ms` NULL (timestamp unparseable even by the
  backfill) sort below every real instant: never the newest, last in
  the trail, pruned first.

## 3. Compatibility / conflict policy (brief item 3)

- **Additive only.** Migration 0003 adds and backfills one column. It
  does not dedupe stored history: legacy same-instant rows in different
  spellings BOTH survive, payloads and spellings byte-identical, now
  sharing one `instant_ms`. The R04 regression proves this on a
  disposable database seeded pre-migration.
- **Same-instant differing payloads:** first-stored wins, deterministi-
  cally. A later delivery of an already-stored instant inserts nothing
  and overwrites nothing, in any spelling — the C05 outcome, generalized
  from string identity to instant identity and now stated as policy.
  No hybrid is ever constructed. The conflict is still not surfaced in
  any response field; presentation remains the deferred C05 item.
- **New deliveries dedupe against legacy rows** through the same
  `instant_ms` check (the backfill makes legacy instants addressable).

## 4. Regression evidence (committed receipt)

`offline/snapshot-audit-r1.mjs` + `offline/snapshot-audit-r1-entry.ts`
run the REAL fixed `getLive` chain over the verbatim 0002+0003 DDL on
drizzle-orm/libsql in-memory storage, with the same disclosed
substitutions as the C1 audit (offline SDK adapter, in-memory fetch
stub; platform schema validation not run). Exit code is non-zero on
any FAIL — this harness verifies a fix, unlike the audit. The committed
receipt from the delivery run is
`offline/snapshot-audit-r1-receipt.json` (sha256 `7574d8601147…`),
binding all 9 cases to the exercised file hashes and dependency
versions (drizzle-orm 0.45.2, @libsql/client 0.14.0, zod 4.4.3,
Bun 1.4.2). **9/9 PASS:**

| Case | Brief row | Result |
| --- | --- | --- |
| R01 equivalent-instant interleave (the C03 sequence, newer frame between spellings) | 2 observations for 2 instants, not 3; old spelling never latest | PASS — 2 rows, fallback = the +60s frame, both stored spellings are the first-seen ones |
| R02 mixed offsets crossing a UTC date boundary, scrambled arrival | order follows parsed instants; raw spellings inspectable | PASS — trail [−05:00, +02:00, Z] in instant order; stored spellings unchanged |
| R03 same-instant differing payload | deterministic policy, no hybrid | PASS — 1 row, first payload (spot 500) kept against the 999 offset replay |
| R04a legacy rows + 0003 in disposable storage | additive migration; no unreported destructive rewrite | PASS — 3 rows in, 3 out, payloads/spellings byte-identical, instants backfilled equal for the spelling pair; a new delivery of the legacy instant dedupes |
| R04b legacy same-instant tie | deterministic | PASS — fallback picks the highest-id row (Z spelling, spot 505) |
| R05 ascending 1501 frames | exactly 1500, newest retained, trail 240 | PASS — retained instants ts(1)..ts(1500) |
| R06 newest-first 1501 frames | same newest-1500 instant SET as ascending; fallback = newest input | PASS — retained set byte-identical to R05's; fallback ts(1500) |
| R07 older arrival at capacity | cannot evict newer or regress fallback | PASS — 1500 retained, min instant unchanged, the old arrival itself pruned, fallback ts(1499) |
| R08 controls | exact replay dedupes; +44 skipped / +45 accepted vs latest persisted instant; 0 vs null distinct; no fabricated fallback | PASS — counts [1,1,2,3], zero/null preserved top-level and per-strike, empty storage honestly empty |

The C1 audit harness (`offline/snapshot-audit.mjs` + entry) is NOT
modified and its receipt stands as the historical record of the
pre-fix behavior; its C03/C08 expectations describe the old source and
are superseded for those two cases by R01/R05–R07 above. C05/C06/C07
behaviors were not re-run because the code paths they exercise are
unchanged by this diff (catch-all and fallback-construction bytes are
identical); R03/R08 cover the parts of C05/C01/C02/C04 the brief's
acceptance table re-tests.

## 5. Preserved evidence lanes (re-run at this revision)

- **SSR lane** (`offline-build.mjs`, production deps): preflight 13/13,
  F1 boundary **51/51**, typecheck clean; all 20 retained preview
  HTML/payload outputs **byte-identical**. `preview/BUILD-MANIFEST.json`
  refreshed minimally: inputs 32 → 33 (actions.ts + schema.ts hashes
  updated, `drizzle/0003_snapshot_instant.sql` added); of 42 outputs
  exactly one hash changes — `server/actions.js`
  (`135798207f65ec19…`), the bundle that embeds the fixed actions.ts.
- **Browser lane** (`browser-fixture.mjs`, production deps): all 9
  cases pass with case HTML and handler responses **byte-identical** to
  the retained packet; 8 controls + aggregation proof 14/14 unchanged;
  the only report deltas are settle timings. `browser-preview/
  BROWSER-MANIFEST.json` is the fresh run's manifest (inputs 32 → 37:
  0003 and the C1/R1 audit companions enter the directory scan; actions/
  schema hashes updated) with its 19 screenshot entries rebound to the
  RETAINED PNG bytes — re-rendered PNGs differed only as raster noise
  and were not adopted, so every output entry verifies against the
  committed bytes (40/40 checked, 0 mismatches). The two omitted
  bundles remain UNAVAILABLE, as before.
- **Backend:** py_compile 12/12; pipeline J1 **50/50** (package
  `pipeline/tests/`), package J1 **27/27**, production-repo J1
  **27/27**; watcher **0 failures**. No pipeline file changes in this
  completion.

## 6. Scope limits (unchanged honesty labels)

Hosted platform DB behavior and platform schema validation remain
UNRUN — the evidence is the packaged source + real SQL semantics on
the declared driver family in disposable storage, same as the audit
this fixes. The migration targets the packaged drizzle chain
(0001 → 0002 → 0003); no production database exists in evidence to
migrate, and none was touched.
