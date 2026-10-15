# ADOPT-F1 — truthful reference-dashboard boundaries

Change note for the ADOPT-F1 assignment (PR #2 comment 6203638946,
2026-10-15), applied on top of the accepted source-intake pin
`5cd1e37df1f7dd4abee254e5a80b08d25e877fcb` in this same lane
(`implementation/0dte-source-20261015`). Scope honored: only the
candidate's normalization/display boundary and its offline tests changed.
No production code outside this package was modified, nothing was
deployed, and the hosted dashboard page was not rebuilt (its source
lives under the artifact builder's flow; this package is the reviewed
candidate). The platform/SDK build remains UNRUN, as held by the review.

## The three boundary defects and their fixes

### 1. Strike GEX: unknown is not zero
`server/src/actions.ts` — `mapStrikes` used `num(...) ?? 0`, collapsing
missing/null/non-numeric GEX into a genuine-looking 0.

- `mapStrikes` now keeps `num()`'s result verbatim: a reported value —
  **including a genuine 0** — stays a number; anything unreported or
  invalid stays `null` (unavailable).
- The `strikeGex` schema fields (`netGexM`, `callGexM`, `putGexM`) are
  now `z.number().nullable()` — the schema tells the truth instead of
  forcing a fabricated zero.
- `normalize` adds **`strikeCoverage`** `{total, gexKnown, gexMissing}`
  over the full by-strike array: explicit coverage evidence.
- Client `GexChart` excludes null-GEX strikes from the series (never
  drawn as zero-height bars) and renders the coverage line ("N of M
  strikes reported — K unavailable, excluded (not zeroed)") when any
  are missing. The top-strikes table renders null as "—" with no
  positive/negative coloring.

### 2. Update clocks: aware, valid, not future — or never LIVE
`updated_at` was admitted as any nonempty string (server) and the
client status selector fell through to LIVE on NaN/negative ages.

- Server `normalize` now requires **`updateClockAcceptable`**:
  `parseAwareInstant` accepts only ISO-8601 strings with an explicit
  timezone (`Z` or `±hh:mm`/`±hhmm`) that `Date.parse` resolves to a
  finite instant; a timezone-less string is rejected outright (the
  missing zone is never inferred from machine locale). An instant more
  than **`MAX_FUTURE_SKEW_MS = 120_000`** (the explicit skew allowance)
  ahead of the receipt clock makes the frame inadmissible — `normalize`
  returns null and the caller keeps serving the last good snapshot.
  The review's synthetic future case (a full day ahead) is rejected.
- `quote_as_of` remains a separate source-observation clock and is not
  gated by the receipt-clock rule.
- Client: `feedAgeMs(updatedAt, nowMs)` returns `null` for an
  unverifiable clock (invalid, naive, or beyond-skew future); small
  negative ages inside the allowance clamp to 0. The status decision
  now lives in the pure **`selectConnStatus`** helper: `ageMs === null`
  selects **STALE, never LIVE**. All previously passing status states
  (paused / down / showing-stale / not-ok / closed / stale-on-age /
  live) are preserved — see the decision-table assertions in the tests.

### 3. Print clustering: true / false / unknown
`client/src/App.tsx` rendered `cluster === true ? CLUSTERING : isolated`,
so legacy rows whose cluster tag is absent (normalized to `null`)
displayed as "isolated".

- New pure helper **`clusterState(cluster, prints60m)`** returns
  `{kind, text}` with three states: `true` → clustering (with the
  prints-in-hour count, or "count unknown"); explicit `false` →
  isolated; `null`/missing → **unknown** ("clustering unknown (legacy
  row)"). Only an explicit false can say "isolated".
- The passing legacy normalizer (`normalizeSignals`, absent tags →
  null) is untouched.

## Tests (offline, portable)

`dashboard-streaming/tests/boundaries.test.mjs` — zero-dependency Node
script. It extracts the marked ADOPT-F1 pure-helper blocks **verbatim**
from the production sources (server actions + client App) and asserts
against the extracted code: GEX zero/null/invalid/coverage, server
clock admission (aware/naive/garbage/future/skew), client age +
full status decision table (incl. end-to-end future and naive clocks
never selecting LIVE), and the three clustering states.

```
node dashboard-streaming/tests/boundaries.test.mjs   →  51 passed, 0 failed
```

Receipts run against this candidate's exact bytes (2026-10-15):

- boundaries.test.mjs: **51/51**
- TypeScript compile integrity: `tsc --noEmit` clean for both client
  and server projects (checked against the production install's
  dependency tree; the platform artifact build itself remains UNRUN
  under the portability hold — no SDK tarball is part of this package).
- Backend preserved: 12 pipeline modules compile; watcher windows
  **12/12**; J1 replay suite **50/50**; `build_signals()` synthetic
  checks unchanged from the accepted pin (missing DB → error payload
  and no file created; empty DB → `empty`; saved session → caps
  10 stacks / 15 extremes with legacy extremes carrying no fabricated
  cluster key; dropped state table → isolated error payload, no
  exception).
