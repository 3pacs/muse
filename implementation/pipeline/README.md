# muse — 0DTE tape stack

Intraday 0DTE options positioning stack: live gamma interpreter, max-pain
tracker, alert watcher, append-only history, queryable tape database, and a
dashboard data builder. Built with Muse.

## Components

- `interpreter.py` — polls the live RTD inputs at `gex.stepdad.finance`
  (`/api/state` quote + `/api/contracts` chain) every 30s, merges Nasdaq
  delayed wings for the full 0DTE chain, and serves derived feeds on :8787:
  `/feed/gamma`, `/feed/flow`, `/feed/vanna-charm`, `/feed/iv`,
  `/feed/maxpain`, `/feed/positioning`, `/feed/all`, `/stream` (SSE).
  Stdlib only, no dependencies.
- `watcher.py` — 2-minute alert checks: max-pain open/move/reversal,
  wall moves, gamma-flip moves, spot crossing max pain. Alerts only on
  genuinely new levels (no flicker re-pings).
- `maxpain_log.py` — appends one record per run (5-min cadence) with
  40+ fields: spot, max pain, walls, flip, regime, pin score, expected
  move (full + remaining), dealer hedge buckets, reversal conditions,
  charm/vanna, volume/OI, IV surface, market-event tags. Also writes
  per-strike GEX snapshots for the heatmap.
- `tape_db.py` — SQLite mirror of the history
  (`snapshots`, `gex_strikes`, `alerts` tables). Backfill + SELECT CLI:
  `python3 tape_db.py "SELECT expiry, MAX(pin_score) FROM snapshots GROUP BY expiry"`.
- `dashboard_build.py` — builds `dashboard_data.json` for the 0DTE
  dashboard artifact (stat cards, ranges, hedge bars, pin gauge, GEX
  heatmap, reversal watch, event pills).
- `maxpain_milestones.py` / `ranges_today.py` — milestone lead/lag
  analysis and intraday range computation.
- `market_events.json` — FOMC/CPI calendar used to tag records.

## Run

```bash
cd ~/workspace/stepdad-0dte
nohup python3 interpreter.py --port 8787 --poll 30 >/tmp/0dte-interp.log 2>&1 &
```

## Data sources

- `gex.stepdad.finance` — real-time gamma feed (3 strikes around ATM).
- Nasdaq public option-chain API — full 0DTE chain, ~15min delayed
  (wing gamma via Black-Scholes at ATM IV).

## Known limitations

- RTD center is only 3 strikes; wings are delayed ~15min.
- GEX sign follows the standard convention (dealers long calls / short
  puts) — an assumption, not observed positioning.
- Nothing here predicts direction; gamma evidence supports vol regime
  and pinning only. See the literature notes before trading on it.
