# Handoff: 0DTE stack → self-hosted on Anik's server

**For:** Anik's server agent (the box behind `gex.stepdad.finance`)
**From:** Muse — 2026-10-15. Supersedes the 2026-10-08 dashboard handoff in full.
**Goal:** Run the complete 0DTE stack — interpreter, feeds, streaming dashboard,
tape logging, indicator tracker, state alerts — on Anik's own server, so the
dashboard lives at a real URL on his domain (e.g. `https://gex.stepdad.finance/dashboard/`)
and can be added to his phone home screen. Today all of it runs on Muse's VM.

## End state

- Dashboard page served from Anik's domain over HTTPS, polling the feeds
  same-origin every 15 seconds, rendering live — no rebuilds, no Muse hosting.
- Interpreter and all data jobs running under supervision on the server.
- `tape.db` + append-only JSONL histories accumulating on the server from cutover.
- Muse's VM copies keep running in parallel until Anik confirms cutover;
  nothing about tonight's deployment changes current alerting.

## Architecture

```
thinkorswim RTD collector (Anik's, already live)
  http://gex.stepdad.finance/api/state       live SPY quote + 1-min bars
  http://gex.stepdad.finance/api/contracts   full 0DTE chain (bid/ask, vol, OI, greeks)
Nasdaq public chain API (api.nasdaq.com)     wide wings, ~15-min delayed, modeled IV
        │
        ▼
interpreter.py  (Python 3, stdlib only, port 8787)
  /feed/all  /feed/gamma  /feed/flow  /feed/vanna-charm  /feed/iv
  /feed/positioning  /feed/maxpain  /feed/signals  /stream (SSE)
        │                                    ▲
        ▼                                    │ reads (read-only)
dashboard page (static HTML/JS)              │
        ▲                                    │
        │ 15s poll, same-origin              │
tape.db (SQLite) ◄── maxpain_log.py (5m snapshots)
        ▲          ◄── indicator_tracker.py (SPY/QQQ/VIX/^TNX events)
        └──────────◄── state_alerts.py (loaded-gun state, charm trigger)
```

## File manifest (source: Muse VM `~/workspace/stepdad-0dte/`)

| File | Role |
|---|---|
| `interpreter.py` | The feed server. Polls the RTD collector + Nasdaq, computes GEX/walls/flip/max pain/positioning/charm/vanna/IV and **speed** (`speed_m_per_pt2`, `speed_wide_m_per_pt2` in the gamma block), serves `/feed/*` + `/stream`. |
| `run_interpreter.sh` | Supervisor: restarts the interpreter ~5s after any exit, append-logs timestamp + exit code. The interpreter must never run unsupervised (it died repeatedly mid-session on 2026-10-14 before supervision). |
| `indicator_tracker.py` | Classic-indicator engine on Yahoo 1-min bars: SPY + QQQ (RSI 1m/5m, Stochastic, MACD, VWAP, volume), VIX module (`^VIX`/`^VIX9D`), rates module (`^TNX`). Detects events, STACKs, EXTREMEs and mega prints; scores forward returns into `tape.db` `indicator_events`. Modes: `--live`, `--backfill YYYY-MM-DD`, `--report`, `--reversals YYYY-MM-DD`. |
| `state_alerts.py` | Loaded-gun state machine + charm trigger over `tape.db` snapshots; writes `state_events`. Modes: `--live`, `--backfill`, `--report`. |
| `maxpain_log.py` | 5-minute snapshot logger → `maxpain_history.jsonl` (append-only, never prune) + mirrors into `tape.db`, writes per-strike `gex_history.jsonl` and flow snapshots. |
| `tape_db.py` | `tape.db` schema/migrations/CLI (init/backfill/stats/SELECT). Tables: `snapshots`, `gex_strikes`, `indicator_events`, `state_events`, `alerts` (schema only). |
| `watcher.py` | Max-pain/wall/flip/directional-move alert logic (in the Muse deployment this is what pings Anik; on the server it is a data job unless Anik wires a notifier). |
| `ranges_today.py`, `maxpain_milestones.py` | EOD ranges note; 5/30/365-day milestone analysis. |
| `dashboard_build.py` | Legacy static-dashboard dataset builder. Not needed by the streaming page; keep for reference. |
| `market_events.json` | FOMC/CPI calendar the logger tags records with. |
| `schwab_client.py` | Read-only Schwab Trader API scaffold (OAuth + SPY chain probe). The planned input upgrade — when Anik's Schwab app is approved, this replaces the 3-live-strike + delayed-wing inputs. Optional at cutover. |
| `test_watcher_windows.py`, `j1_replay_tests.py`, `tests/` | Regression tests; run after any watcher/interpreter change. |

All Python is **stdlib only** — no pip installs. Python 3.10+ (zoneinfo).

## Feed contracts

### `GET /feed/all`
One payload: `status, updated_at, market_open, quote_as_of, spot, expiry,
n_strikes, n_strikes_rtd_live, n_strikes_nasdaq_delayed, sources`, plus blocks:
`gamma` (net_gex_m, gamma_flip + method/roots/residuals diagnostics, call_wall,
put_wall, regime, by_strike, top_strikes, max_pain, **speed_m_per_pt2,
speed_wide_m_per_pt2, speed_note**), `flow`, `vanna_charm`, `iv`, `positioning`
(expected move, hedge buckets, pin score). Poll cadence in the current
deployment: snapshot rebuild every ~30s; page polls every 15s.

### `GET /feed/signals` (added 2026-10-14)
Read-only query over `tape.db`; returns the **most recent session present in
the DB** (so overnight it shows the last session, labeled). Failure-proof: any
DB problem returns `{"status":"error", ...}` with empty lists — it must never
take the interpreter down.

```json
{
  "status": "ok",
  "day": "2026-10-14",
  "generated_at": "2026-10-15T06:40:56+00:00",
  "loaded_gun": {"active": false},
  "last_charm_trigger": {"ts_et": "2026-10-14 11:42", "spot": 770.48, "charm_vel30": -18280.2},
  "stacks":   [{"ts_et": "2026-10-14 12:30", "symbol": "SPY", "direction": "bull",
                "spot": 769.47, "detail": {"members": ["vwap_stretch@12:15", "rsi1_reversal@12:20", "stoch_cross@12:30"], "path": "A"}}],
  "extremes": [{"ts_et": "2026-10-14 15:19", "symbol": "SPY", "type": "vol_ignition",
                "direction": "bull", "spot": 768.05,
                "detail": {"vol": 1093229, "median30": 76649, "mult": 14.3}}]
}
```

- `loaded_gun` when active: `{active: true, since_et, spot, budget_left, pin, net_gex_m, flip_dist}`.
- `stacks`: up to 10 most recent `STACK` rows for the day, chronological.
- `extremes`: up to 15 most recent rows whose type ∈ {rsi_extreme, vwap_stretch,
  vol_ignition, vix_spike, vix_rollover, vix_divergence, vix_term_stress,
  yield_spike, yield_rollover}, chronological.
- **Print rows** (`type == "vol_ignition"`) written by current tracker versions
  also carry in `detail`: `mega` (bool), `at_lows` / `at_highs` (bool),
  `cluster` (bool — another print within the prior 30 min, same symbol),
  `prints_60m` (int), `budget_left` (float|null). Rows stored before
  2026-10-14 carry only `{vol, median30, mult}` — render missing tags as absent,
  never as false.

### Signal definitions (so the page labels mean something)
- **STACK**: ≥3 distinct same-direction indicator events within 15 min
  including a core signal (RSI divergence or stochastic cross), or
  divergence + structure within 20 min.
- **Mega print**: one minute of SPY volume ≥ 800k shares (QQQ ≥ 400k) **and**
  ≥ 4× the trailing-30-minute median. Raw volume pours in toward the close;
  the absolute floor alone is not abnormal late in the day.
- **Loaded gun**: expected-move budget_left > 0.50 AND pin score < 40 AND
  net GEX < 0 AND spot below the gamma flip (2-row exit hysteresis).
  Direction is NOT part of the signal.
- **Charm trigger**: charm velocity (30m) ≤ −10,000 while the loaded-gun
  state is on.
- **Speed**: d(dealer gamma $M/pt)/dSpot, central differences ±1pt (±2pt for
  wide), frozen IV/OI. Accrues only from live sessions — cannot be backfilled.

## Dashboard page spec

Single static page (HTML/JS, no build step) served same-origin with the feeds
(reverse-proxy `/feed/*` to `127.0.0.1:8787`). Poll `/feed/all` and
`/feed/signals` every 15s while open. Panels:

1. **Header/status**: spot, expiry, LIVE / STALE / FEED DOWN / MARKET CLOSED
   derived from `updated_at` age + `market_open`; Pause/Resume + manual Refresh.
2. **Levels ladder**: call wall, gamma flip, max pain, put wall vs spot.
3. **Net GEX by strike** bars (`gamma.by_strike`), top strikes.
4. **Positioning**: pin score gauge, expected move (full + remaining),
   dealer hedge buckets (±10/25/50bp, ±1%).
5. **Intraday trail**: spot vs flip/walls from the page's own throttled
   snapshots (max 1/min, keep ~3 trading days client-side).
6. **Flow/IV**: put/call volume + OI ratios, hottest strike, unusual prints,
   ATM IV, 25d risk reversal, smile.
7. **Signals panel** (from `/feed/signals`): loaded-gun banner (prominent when
   active: since, spot, pin, net GEX, budget %; quiet "Loaded gun: off" when
   not), last charm trigger line, **speed readout** (`Speed: {speed_m_per_pt2}
   / wide {speed_wide_m_per_pt2} $M/pt²`, "—" when null), stacks list
   (time ET, symbol, direction, spot, members joined " + "), extremes & prints
   list (prints get a 🖨️ row: comma volume, ×median, MEGA badge,
   "⚠️ CLUSTERING (n in last hour)" when `cluster` else "isolated",
   at-lows/at-highs word). If `/feed/signals` errors, show a muted
   "signals unavailable" — never break the rest of the page.
8. Mobile-first layout (primary use is Anik's phone), dark theme, and the
   usual home-screen meta (`viewport`, `theme-color`,
   `apple-mobile-web-app-capable`) so Add to Home Screen gives a clean icon.

## Scheduling & supervision on the server

- **Supervisor (required)**: run `run_interpreter.sh` under systemd
  (`Restart=always`, `WorkingDirectory` = code dir, stdout appended to a log
  file — append, never truncate: crash traces and supervisor exit codes are
  the diagnostics). Start the supervisor, never the bare interpreter.
- **cron** (America/Los_Angeles):
  - `*/5 * * * *` → `python3 maxpain_log.py` (silent snapshot logger)
  - `*/2 * * * *` → `python3 watcher.py` (alert logic; notifier = Anik's choice)
  - `*/2 * * * *` → `python3 indicator_tracker.py --live && python3 state_alerts.py --live`
  - `5 13 * * 1-5` → EOD ranges (`ranges_today.py`)
  - `15 13 * * 1-5` → `python3 maxpain_milestones.py`
  - Fallback rule inside the 2-minute jobs: if `pgrep -f interpreter.py`
    finds no interpreter, start the supervisor once — never a second instance.

## Porting changes (do these before first run)

The code was written for Muse's VM; repoint every absolute path:
- `interpreter.py`: `TAPE_DB` constant (currently
  `/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db`).
- `indicator_tracker.py`: `DB_PATH`, `JSONL_PATH`.
- `state_alerts.py`: `DB_PATH`.
- `tape_db.py`: `HIDDEN` base dir; `maxpain_log.py` + `watcher.py`: history
  file paths. Easiest check: `grep -rn "/home/hatch" *.py` must return nothing.
- Choose the server data dir (e.g. `/var/lib/0dte/`) holding `tape.db`,
  `maxpain_history.jsonl`, `gex_history.jsonl`, `flow_history.jsonl`,
  `indicator_events.jsonl`. **Histories are append-only — never prune,
  rotate-truncate, or "clean up" old rows.**
- Port `8787` is the default everywhere (`--port` flag exists); keep the
  interpreter on loopback and expose it only through the reverse proxy.

## Cutover checklist

1. Copy code + `market_events.json`; apply path changes; `python3 -m py_compile *.py`.
2. `python3 tape_db.py` init on an empty data dir (schema + migrations).
3. Start supervisor under systemd; verify `curl localhost:8787/feed/all`
   returns `status: ok` during market hours.
4. Enable crons; after one session verify: snapshots accruing in `tape.db`,
   JSONLs appending, `/feed/signals` returns the session's stacks/extremes.
5. Kill test: `kill` the interpreter PID → supervisor restarts it within
   ~10s and the exit is logged.
6. Parallel-run one full session against Muse's VM feed; compare `/feed/all`
   spot/max pain/flip/regime (exact match expected on spot and max pain;
   flip is a zone — small differences are methodology noise already present
   between engines).
7. Serve the page at the chosen URL; Anik adds it to his home screen.
8. Anik confirms → Muse disables the VM crons and the VM stack stands down.

## Decisions for Anik

- **URL**: path (`gex.stepdad.finance/dashboard/`) vs subdomain.
- **Access**: the RTD collector's existing GEX view is non-authenticated and
  the feeds have no auth. Options: leave open, HTTP basic auth at the proxy,
  or tailnet/VPN-only. The dashboard reveals positioning derived from his own
  feed — his call; no default chosen here.
- **Alerting**: in the Muse deployment, watcher/tracker/state outputs are
  relayed to Anik by Muse's crons. On the server these are just stdout —
  decide whether alerts stay with Muse (reading the server's feed/DB
  remotely) or move server-side (ntfy/webhook/etc.).

## Known limitations (carry these into any future work)

- Only 3 strikes are real-time (RTD); the other ~148 come from Nasdaq
  ~15-min delayed with modeled IV. Spot and max pain are solid; the gamma
  flip is a zone, not a line; walls are methodology, not fact. Schwab
  (above) is the fix.
- Yahoo 1-min bars (tracker input) intermittently arrive in a corrupted
  variant with phantom 10–30M-share minutes; the tracker fetches up to 3
  variants, keeps the cleanest, and sanitizes remaining outliers. Prices
  are unaffected.
- `speed` cannot be backfilled — it needs the live chain. It starts
  accruing on the server's first live session.
- The interpreter must not run twice against the same `tape.db`
  (WAL contention + duplicate snapshots). One supervisor, one instance.
