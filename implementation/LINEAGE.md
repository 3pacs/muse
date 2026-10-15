# Lineage — against reviewed pin `6ffff8ab` and repo history

Requested: lineage of this implementation against the reviewed
`6ffff8ab6af60d90e624e3b1af333f6bbc2ca077` (LIVE-G1-DELIVERY-R4,
branch `redteam/ui-g3`).

## The honest answer

`6ffff8ab` is the tip of the **reviewed delivery-candidate line**
(`live-g1/delivery/` UI + adapter). That line was **never merged and
never became the production system**. The production stack packaged
here descends from **repo main `43c2cd41`** (2026-10-04, "0DTE tape
stack: interpreter, watcher, logger, tape DB, dashboard builder") and
evolved in place in the production workspace from 2026-10-05 through
2026-10-15. The two lines share the Oct 4 ancestors and the Oct 5
R1–R9 fix cycle; after that they diverge:

- **Backend (logger/DB):** the J1…J1-F acceptance work happened on
  `redteam/fixes-*` branches. Those branches are not ancestors of the
  production files, but the production `maxpain_log.py` / `tape_db.py`
  **pass the full 50-test J1 suite** (`pipeline/tests/j1_replay_tests.py`,
  run against the exact bytes in this package — see TESTS.md). The
  production files additionally carry later features the branch line
  never had (speed columns, positioning, signals support), which is
  why raw diff counts against both main and `fixes-r1-r9` are large.
- **Interpreter:** production `interpreter.py` is closest to
  `redteam/fixes-r1-r9` (`e201a45c`, the R1–R9 fix return): ~101
  changed lines, vs ~390 against main. The delta is the Oct 12–14
  production work: `/feed/signals`, speed (3rd-order Greek),
  positioning/reversal reads.
- **Watcher:** descends from main's watcher with the Oct 12
  displacement-window fix (12/12 synthetic checks) and the Oct 15
  `wall_break` alert. The R1–R9 branch did not touch it.
- **New modules with no repo ancestor:** `indicator_tracker.py`,
  `state_alerts.py`, `wall_tests.py`, `run_interpreter.sh`
  (supervisor, adopted 2026-10-14), `schwab_client.py` (scaffold).
  All were built in the production workspace Oct 12–15 and are
  published here for the first time.
- **Dashboard:** the reviewed `6ffff8ab` delivery page is a *separate
  candidate* that was never deployed. The production page is the Muse
  streaming artifact (`dashboard-streaming/` in this package, slug
  `0dte-streaming-dashboard`, built 2026-10-12, Signals panel added
  2026-10-14) plus the legacy static EOD page whose data builder is
  `pipeline/dashboard_build.py`. The Oct 15 self-host handoff
  (`docs/0DTE-SELF-HOST-HANDOFF.md`, commit `4ce50f57`) specifies
  re-implementing this page for self-hosting; until that cutover
  happens, **the handoff document is a specification and this package
  is the implementation it specifies from**.

## Diff summary (production file vs repo refs, changed lines)

| File | vs main `43c2cd4` | vs `fixes-r1-r9` `e201a45c` |
|---|---|---|
| interpreter.py | 390 | 101 |
| maxpain_log.py | 393 | 373 |
| tape_db.py | 816 | 809 |
| dashboard_build.py | 93 | 3 |
| watcher.py | 97 | 97 (branch did not touch it) |

Measured 2026-10-15 with `diff` on the exact packaged bytes.
