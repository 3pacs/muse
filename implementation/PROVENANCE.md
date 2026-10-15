# Provenance — ownership, data, clocks, units, schemas

## Ownership and license

All pipeline code (`pipeline/`) was authored by Muse (Meta) working
for the repository owner in the owner's workspace, 2026-09-28 through
2026-10-15. No third-party code is vendored into the pipeline: it runs
on the Python 3 standard library only (`http.server`, `sqlite3`,
`urllib`). The streaming dashboard (`dashboard-streaming/`) is a
TypeScript/React application built on the Muse artifact platform; its
third-party dependencies are exactly those in its `package.json`
(React and platform libraries, each under its own license in its
npm package). No credentials, account identifiers, personal
positions, or private operational data are included in this package;
API access in the optional components is read from environment
variables at runtime and no keys exist in the tree.

## Data sources and display rights

The interpreter assembles its snapshot from three sources, each
labeled in-band on every payload (`sources` block of `/feed/all`):

- **RTD feed** (`gex.stepdad.finance`): real-time quotes for 3 strikes
  around the money. Delay label: `realtime`.
- **Nasdaq public option-chain API**: the remaining ~148 strikes,
  ~15-minute delayed, IV modeled. Delay label: `~15min`.
- **Yahoo Finance 1-minute bars**: used by the indicator/state/wall
  engines (SPY/QQQ/VIX/VIX9D/^TNX). Yahoo intermittently serves a
  corrupted variant with phantom 10–30M-share minutes; the shared
  `fetch_bars` sanitizer keeps the least-phantom variant and replaces
  residual >5M mid-session bars with the trailing median (documented
  in `indicator_tracker.py`).

These are the owner's own data subscriptions/feeds used for personal
display. Nothing in this package redistributes market data; the
fixtures are synthetic.

## Clocks

Two clocks ride on feed data and the distinction is contractual:

- **Source clock** (`quote_as_of`, per-source `as_of`): when the
  upstream data was current.
- **Receipt clock** (`updated_at`, `generated_at`, `logged_at`): when
  this system received/computed it.

`/feed/signals` rows carry `ts_utc` + `ts_et`. Tape records keep the
original timestamp (`ts`, plus `ts_original` where a repair rewrote a
row — see the J1 policy doc).

## Units and formula versions

- **GEX**: formula `v2`, units **USD millions per 1% spot move**
  (`gex_formula` / `gex_units` are stamped on every record; the v1→v2
  unit change is why mixed-vintage consumers must check the stamp).
- **Gamma flip**: `spot_root_frozen_iv_oi` — root of net gamma over a
  spot grid with IV/OI frozen; roots and residuals are in the payload.
- **Speed**: $M per point² — d(dealer gamma)/dSpot, central
  differences (±1pt `speed_m_per_pt2`, ±2pt `speed_wide_m_per_pt2`)
  on the same frozen solver. Accrues from 2026-10-15; not backfillable.
- **Expected move**: the quoted ATM straddle (`dollars_kind: quoted`);
  "remaining" equals the quote — the sqrt(time) rescale was removed
  (R8), and `remaining_kind` says so.
- **Vanna**: $ thousands per +1pt IV. **Charm**: $ thousands per hour.
  Dealer-position assumption (long calls / short puts) is stated
  in-band in `vanna_charm.assumptions` and `positioning.assumptions`.
- **Pin score**: 0–100, components in-band (`pin_components`).

## Database DDL and migrations

SQLite `tape.db`, schema owned by the writers, all
`CREATE TABLE IF NOT EXISTS` (additive, no migration framework):

- `snapshots`, `gex_strikes`, `alerts`, `mirror_conflicts` —
  `pipeline/tape_db.py` (`connect()`); column additions are
  try/except `ALTER TABLE` migrations in the same file (e.g. the
  2026-10-14 speed columns).
- `indicator_events` (+ `indicator_events_v2` staging in the same
  module) — `pipeline/indicator_tracker.py`. Unique key
  `(ts_utc, type, direction, symbol)` is the dedup contract.
- `state_events` — `pipeline/state_alerts.py`. Unique `(ts_utc, type)`.
- `wall_tests` — `pipeline/wall_tests.py`. Unique
  `(day, ts_utc, side, kind)`; outcomes mature in place from
  `pending` to `accepted`/`rejected`.
- The streaming dashboard has its own store (snapshot throttling for
  the intraday trail): `dashboard-streaming/drizzle/0001_initial.sql`,
  `0002_snapshots_table.sql`.

## JSONL archives (append-only; the raw record under tape.db)

Written every 5 minutes by `pipeline/maxpain_log.py`:

- `maxpain_history.jsonl` — one record per snapshot, **57 keys**
  (verified on the 2026-10-15 tail record): identity/time (`ts`,
  `ts_original`, `logged_at`, `expiry`, `market_open`), source clocks
  (`quote_as_of`, `nasdaq_as_of`, `src_mix`), levels (`spot`,
  `max_pain`, `call_wall`, `put_wall`, `gamma_flip`, `gamma_regime`,
  `pin_score`, `pin_magnet`), gamma (`gex_m`, `net_gex_m`,
  `gex_formula`, `gex_units`, `dealer_gamma_m_per_pt`,
  `speed_m_per_pt2`, `speed_wide_m_per_pt2`, `top_gamma`), hedge
  buckets (`hedge_25bp_m/_dir`, `hedge_1pct_m/_dir`), expected move
  (`exp_move_dollars/_pct`, `exp_move_rem_dollars/_pct`), flow
  (`call_volume`, `put_volume`, `call_oi`, `put_oi`, `pc_volume`,
  `pc_oi`, `hottest_strike`, `hottest_call_vol`, `hottest_put_vol`,
  `unusual_count`, `unusual_notional_k`, `top_unusual`), IV
  (`atm_strike`, `atm_iv`, `atm_put_iv`, `rr_25d`, `smile_width`,
  `smile_min_strike`), second-order (`vanna_k`, `charm_k`), reversal
  watch (`rev_magnet`, `rev_disp_dollars`, `rev_stretched`,
  `rev_conditions`), and `events` (market-calendar tags).
- `gex_history.jsonl` — per-snapshot strike map:
  `{ts, expiry, spot, gex_m: {strike: value}, gex_formula, gex_units}`.
- `flow_history.jsonl` — `{ts, expiry, spot, elevated, top_volume}`.

## Replay / dedup behavior

The logger mirrors each accepted record into tape.db. The mirror is
**digest-verified**: a replay may repair a divergent projection but
may never alter accepted content, and a payload whose digest cannot be
proven is quarantined rather than merged (full semantics:
`pipeline/docs/J1-EVENT-REPLAY-POLICY.md`; enforced by the 50-test
suite in `pipeline/tests/`). JSONL is append-only and never pruned;
`ts_original` preserves pre-repair identity. Indicator/state/wall
engines dedup on their unique keys above, which is also what makes
their `--live` output safe to relay exactly once.
