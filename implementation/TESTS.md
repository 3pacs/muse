# Test receipts — exact packaged source

All runs executed 2026-10-15 against the **exact bytes in this
package** (the staged tree that was hashed into SHA256SUMS.txt),
Python 3, no network access required by any test.

| # | Command (from `implementation/pipeline/`) | Result |
|---|---|---|
| 1 | `python3 -m py_compile interpreter.py watcher.py maxpain_log.py tape_db.py indicator_tracker.py state_alerts.py wall_tests.py dashboard_build.py ranges_today.py maxpain_milestones.py schwab_client.py test_data_keys.py` | **OK** — all 12 modules compile |
| 2 | `python3 test_watcher_windows.py` | **0 failures** — 12/12 synthetic checks (slow-drift and gap cases no-fire; real 15m/30m up/down moves fire; wall_break arming included in the same harness family) |
| 3 | `python3 tests/j1_replay_tests.py` | **50/50 pass** — the full J1…J1-F accepted-event replay/recovery suite against production `maxpain_log.py` + `tape_db.py` |
| 4 | `python3 j1_replay_tests.py` (root copy) | **27/27 pass** — the earlier suite revision |
| 5 | `python3 wall_tests.py --report` | smoke OK — reads tape.db `wall_tests` (2026-10-15 rows: 765 put defense, 765/768 put breaks, 772 call defense 3.5×, 772 call break 2.2×) |
| 6 | `python3 state_alerts.py --report` | smoke OK — `loaded_gun_on n=10, 7/10 exc60 ≥ $1.39`; `charm_trigger n=7, 5/7`; `charm_vel n=40` ≈ base rate (matches the documented backtest character) |
| 7 | `python3 indicator_tracker.py --report` | smoke OK — per-type forward stats from tape.db `indicator_events` |

Notes:

- Tests 5–7 are read-only reports over the production tape.db; they
  verify the packaged readers against real accumulated state, not
  synthetic fixtures.
- The wall-break state machine in `watcher.py` was additionally
  verified 2026-10-15 against a synthetic feed (8/8 cases: open-only,
  break, quiet, re-arm at $0.25, re-break, pin-cross + put-wall break)
  before it shipped; the harness for that run was ad hoc and is not
  in this package — the durable checks are tests 2–4 above.
- No test in this package places trades, moves funds, or polls a
  provider; the optional Schwab/Tradier/Massive utilities require
  keys that do not exist in this environment and were compile-checked
  only (test 1).
