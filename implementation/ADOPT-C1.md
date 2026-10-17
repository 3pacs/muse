# ADOPT-C1 — offline snapshot persistence/fallback audit

Audit (no application fix, per the brief) of the streaming
dashboard's saved-trail and stale-fallback path, implemented on top
of the accepted ADOPT-E1 pin `0e37a442`. Subject:
`server/src/schema.ts` (snapshots table), `maybePersistSnapshot` /
`loadTrailAndLatest` / `getLive` in `server/src/actions.ts`, and the
response fields the trail/fallback UI consumes. Source declares a
45-second persistence gap (`MIN_SNAPSHOT_GAP_MS = 45_000`), 1500-row
retention (`MAX_SNAPSHOTS = 1500`), and a 240-row trail.

**Result: 3 PASS, 2 OBSERVED classifications, 3 COUNTEREXAMPLES**
(C03 instant identity/ordering, C06 silent persistence failure,
C08 retention semantics). No counterexample is relabeled a pass;
no application code was changed. The runnable companion is
`dashboard-streaming/offline/snapshot-audit.mjs` (+
`snapshot-audit-entry.ts`); verdicts reproduced identically on two
consecutive runs.

## Method — what actually ran

Real production code end to end: the `getLive` handler drives the
real `fetchFeed → normalize` (including the ADOPT-F1 pure helpers)
`→ maybePersistSnapshot → loadTrailAndLatest` chain against the
real drizzle schema, with the table created by the verbatim
`drizzle/0002_snapshots_table.sql` DDL, on drizzle-orm 0.45.2 /
@libsql/client 0.14.0 / zod 4.4.3 under Bun 1.4.2. Storage is
in-memory (`:memory:`), fresh per case. Complete substitution list
(nothing else is substituted):

1. `@hatch/space-sdk` → the lane's fixture adapter
   (`offline/adapter`: defineAction identity, real zod). Platform
   request/response schema validation therefore does not run;
   handler return values are inspected raw.
2. `globalThis.fetch` → an in-memory stub answering only the two
   `/feed/all` URL shapes from a per-step plan; any other URL
   throws. No real feed URL was contacted (the stub log in the
   receipt lists exactly the two feed URL strings, both served
   by the stub).
3. `ctx.db` → a drizzle LibSQL database on in-memory storage (the
   platform's declared db type), instead of the preview lane's
   in-memory fake chain — so uniqueness, TEXT ordering, and
   pruning below are real SQL behavior, not a model of it.
4. C06 only: the `ctx.db` accessor returns a Proxy over the real
   db whose `insert` throws one labeled non-unique error
   (synchronous at the call; production's catch is agnostic to
   sync/async failure).

Fixture source timestamps are generated relative to the audit's
receipt wall clock (recorded per case in the receipt) and always
in the past, so the F1 future-skew gate evaluates them as
production would; no clock is frozen. Each case's generated
fixtures are written to the output directory and hashed in the
receipt (`snapshot-audit-receipt.json`).

Run it:

```sh
node implementation/dashboard-streaming/offline/snapshot-audit.mjs \
  --deps <node_modules from this package's bun.lock> --out <dir>
```

## Results

| Case | Expected contract | Observed (raw) | Verdict |
|---|---|---|---|
| C01 baseline | Two frames 60s apart persist; zero stays numeric, null stays unavailable in columns, trail and fallback | 2 rows; trail ascending; fallback = frame 2 with `netGexM` 0 (number), `gammaFlip` null, strike-level 0 and null preserved | **PASS** |
| C02 exact replay | Identical frame redelivered changes nothing | 1 row after 3 deliveries; fallback identity = the single frame; trail 1 | **PASS** |
| C03 equivalent instants | One instant = one observation under any aware spelling; latest/trail by instant | See counterexample 1 | **COUNTEREXAMPLE** |
| C04 out-of-order/gap | Persistence follows the 45s gap from the latest persisted source time; trail/fallback by source time | +44s skipped, +45s persisted (gap measured from latest *persisted* frame), +46s persisted; late older arrival inserts (negative parsed gap bypasses the throttle); with uniform Z spellings, trail ascending and fallback = newest | **PASS** |
| C05 conflicting replay | Conflict surfaced or resolved by a stated rule; never a hybrid | Stored row keeps the ORIGINAL payload (spot 765.00) in both paths; live responses during conflicts report the feed's changed values (766.50, then 769.99); no response field signals a conflict | **OBSERVED — silently ignored** |
| C06 storage failure | A failed write is not certified as a successful persisted observation | See counterexample 2 | **COUNTEREXAMPLE** |
| C07 malformed newest payload | No invented last-good or live claim; availability/time/reason separately visible | Fallback payload null in all sub-cases, `ok` stays false, empty storage is a clean honest empty; qualifications in finding 3 | **OBSERVED — contract holds with qualifications** |
| C08 retention boundary | Exactly the newest 1500 rows by source time retained; trail 240; fallback newest | See counterexample 4 | **COUNTEREXAMPLE** |

## Counterexample 1 — C03: identity and ordering are the timestamp STRING, not the instant

Frames: instant I = `2026-10-16T23:30:00.000Z` (spot 700.1), the
same instant spelled `2026-10-17T01:30:00+02:00`, and I+60s as Z
(spot 700.2). Both spellings parse to the same instant
(`Date.parse` equal). Row counts: 1 (Z) → 1 (offset spelling;
skipped only because the *parsed* gap is 0 < 45s — a side effect
of the throttle, not dedupe) → 2 (I+60s) → **3** (offset spelling
again: it is no longer the string-max row, the parsed gap is
negative so the throttle does not apply, and the string differs
from the stored Z row so the UNIQUE constraint does not fire —
a second row for one instant). Ordering is `ORDER BY updated_at`
on a TEXT column, i.e. lexicographic: `2026-10-17T01:30:00+02:00`
sorts after every `2026-10-16T…` string, so the trail lists the
older instant last and the feed-down fallback reports
`staleSnapshotAt = "2026-10-17T01:30:00+02:00"` with spot 700.1 —
an older frame presented as the newest, its time mislabeled —
while the chronologically newest frame (700.2) sits in storage.
Smallest repro: the C03 sequence in the companion. Severity:
moderate; triggers whenever feed clocks mix offset spellings
across a UTC date boundary (F1 admits both spellings).

## Counterexample 2 — C06: persistence failure is silent and indistinguishable from the uniqueness race

`maybePersistSnapshot` wraps its insert in a catch-all whose
comment assumes a unique-constraint race. With one injected
non-unique storage failure, the `getLive` response during the
failure is `ok: true`, `feedError: null`, live payload present —
and **0 rows persisted**, trail length 0 on that same response.
Nothing in any response distinguishes success, genuine race
(driver-level: `SQLITE_CONSTRAINT_UNIQUE: UNIQUE constraint
failed: snapshots.updated_at`), and storage failure; the frame
persists only when redelivered after recovery, under its
original source time. Severity: moderate — a storage outage
during live polling leaves silent, unflagged gaps in the saved
trail while every response reads fully successful.

## Finding 3 — C07: no fabrication, but one corrupt row disables payload fallback

(a) Newest row with unparseable `payload_json`: trail still
serves both points from scalar columns (including the corrupt
row's spot 999.99), but the fallback payload is null — the code
does not step back to the older valid payload. `staleSnapshotAt`
still advertises the corrupt row's time next to the null payload,
and no field gives a reason (feedError describes the feed, not
the snapshot). (b) A payload that parses but whose inner
`updated_at` is timezone-less is likewise rejected by
`normalize()` (F1 gate): payload null, time advertised. (c)
Empty storage: clean honest empty (`ok:false`, all snapshot
fields null, trail []). Severity: low — honesty holds;
availability and diagnosability are reduced.

## Counterexample 4 — C08: retention is 1499 at the crossing, keyed by insertion order

1501 frames at 46s spacing through the real handler. After the
1501st insert the retained count is **1499, not 1500**: the prune
deletes `id <= ids[length − 1500]`, removing two rows at the
first crossing (the two earliest-inserted frames), then
oscillates 1499/1500. The pruning key is the autoincrement id —
insertion order, not source time: a late arrival older than every
retained row then inserts, takes the highest id, and is
**retained** (final retained source range starts *before* the
post-prune range), while chronologically newer frames were
pruned earlier. Trail (240, ascending) and the newest fallback
are correct in this run only because the newest frame also
arrived last. Severity: low for the off-by-one count, moderate
for the semantics — "newest" in the code comment means "most
recently inserted", which diverges from source time exactly in
the late-arrival situations C04 exercises.

## Preserved evidence

No production source changed (companion + this note + TESTS.md +
package manifests only). Re-run unchanged at this candidate:
ADOPT-F1 boundary tests **51/51**, backend py_compile 12/12,
watcher **0 failures**, J1 **50/50**, root J1 **27/27**. The
accepted browser packet (B2-R2/E1) is byte-untouched.

## Hashes

| File | SHA-256 |
|---|---|
| offline/snapshot-audit.mjs | `9773e6670bf4841578e4cd30e9b2bcdb293f40f04ed4d46b588c9fd84a97fd53` |
| offline/snapshot-audit-entry.ts | `9b72d4fe7b37e34d8d86ca6d3f16dc4fada00889111722f25d5cbd009ce5b5eb` |
| server/src/actions.ts (exercised, unchanged) | `d6d8ccd134928e9b2e68219c1525105097f9a15d62696bd4df3eb6699a02e266` |
| server/src/schema.ts (exercised, unchanged) | `a6d397b4f9ed6651468a9535b3ba8cbba6cf687649d6cf717115c13d439802ca` |
| drizzle/0002_snapshots_table.sql (executed verbatim) | `c8cc1f77d28ab53a61b81ee354b3ccf0584c639ce4b9a6ad2060ad49f39a0791` |

Per-case fixture hashes and full raw observations are in the
run's `snapshot-audit-receipt.json` (regenerated on every run;
fixture source times are receipt-relative, so hashes of time-
bearing fixtures differ across runs while verdicts reproduce).

## Limits

In-memory libsql is the platform's declared driver family, not
the hosted platform database itself; hosted persistence behavior
is UNRUN. Platform action schema validation is not exercised
(adapter identity). Wall-clock collection behavior, trading-day
coverage, and any hosted deployment claim are out of scope, as
briefed. Application changes, if wanted, are a separate follow-up
— this audit stops at evidence, as instructed.
