# Manifest — per-file SHA-256

Every file in this package, hashed over the exact bytes committed.
`SHA256SUMS.txt` (same directory) carries the full-length hashes in
`sha256sum -c` format. This manifest and SHA256SUMS.txt are themselves
excluded from the sums — they are anchored by the commit that carries
them; verify any file against either list after checkout.

| File | Bytes | Lines | SHA-256 (first 16) | Status |
|---|---|---|---|---|
| `implementation/LINEAGE.md` | 3108 | 60 | `4700872e024a90fe…` | package document |
| `implementation/PROVENANCE.md` | 6251 | 124 | `483d1ef1c1f27e8c…` | package document |
| `implementation/README.md` | 2598 | 53 | `ae5281bd2f7563ff…` | package document |
| `implementation/TESTS.md` | 2262 | 30 | `e5349f627bb6af54…` | package document |
| `implementation/dashboard-streaming/client/build.mjs` | 361 | 10 | `e828666e5d505cbc…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/index.html` | 666 | 19 | `9dcbb078cafc494d…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/src/App.tsx` | 44568 | 1175 | `40ad4559ab9290ff…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/src/api.ts` | 935 | 20 | `b37eff4d0ae161ae…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/src/globals.d.ts` | 24 | 1 | `35d26ea66c86da97…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/src/main.tsx` | 1151 | 28 | `300d8cb852036ce5…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/src/theme.css` | 1832 | 89 | `9010d6975fb6aa97…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/client/tsconfig.json` | 430 | 15 | `d9cc6609a832013b…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/drizzle/0001_initial.sql` | 118 | 5 | `f80c5bf6f7a9bf54…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/drizzle/0002_snapshots_table.sql` | 410 | 17 | `c8cc1f77d28ab53a…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/package.json` | 958 | 29 | `4d696901960aceba…` | dashboard dependencies (third-party, see PROVENANCE.md) |
| `implementation/dashboard-streaming/server/src/actions.ts` | 21197 | 670 | `a18c3ca65c20b90c…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/server/src/schema.ts` | 1231 | 33 | `a6d397b4f9ed6651…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/server/tsconfig.json` | 343 | 14 | `5698f6c130a85287…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/dashboard-streaming/space.json` | 193 | 8 | `42c437360506bc61…` | Muse artifact descriptor (slug 0dte-streaming-dashboard) |
| `implementation/dashboard-streaming/tsconfig.base.json` | 635 | 24 | `1000b5fb48cee172…` | production — streaming dashboard source (Muse artifact platform build) |
| `implementation/fixtures/README.md` | 1839 | 18 | `919c780766fc516a…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_all_error.json` | 225 | 10 | `ad8d32e6cf919c01…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_all_last_session.json` | 4860 | 195 | `24ae7c2b5b8edd03…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_all_success.json` | 4854 | 195 | `5ea638c1af760a8f…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_signals_error.json` | 201 | 11 | `8f4adbe4ca401fc6…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_signals_legacy_tags.json` | 1434 | 68 | `c10216308c266314…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/feed_signals_success.json` | 1780 | 83 | `22caca247eb69953…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/fixtures/sse_stream_sample.txt` | 1381 | 18 | `00e5818113cccd33…` | SYNTHETIC fixture — invented values, exact schema (see fixtures/README.md) |
| `implementation/pipeline/README.md` | 2376 | 52 | `cccf186bfb370486…` | original stack readme (2026-10-04) |
| `implementation/pipeline/dashboard_build.py` | 10235 | 257 | `9534b75b1cfe5714…` | production — data builder for the static EOD dashboard page |
| `implementation/pipeline/docs/J1-EVENT-REPLAY-POLICY.md` | 14145 | 331 | `950645f316f6deb8…` | policy doc — accepted-event replay/recovery semantics for the logger/DB mirror |
| `implementation/pipeline/flow_capture_patch.md` | 3391 | 65 | `9031607571148ef2…` | design note — flow-history capture (implemented in interpreter/logger) |
| `implementation/pipeline/indicator_tracker.py` | 37913 | 787 | `8f50ab4a681c6c81…` | production — classic-indicator engine (SPY/QQQ/VIX/rates), stacks + extremes |
| `implementation/pipeline/interpreter.py` | 43368 | 949 | `e4f347860ef976ab…` | production — core feed service (:8787, /feed/*, /stream, /feed/signals) |
| `implementation/pipeline/j1_replay_tests.py` | 16749 | 430 | `9377aa34e91c8afe…` | regression suite — earlier 27-test copy at repo-root position; superseded by tests/j1_replay_tests.py, kept for lineage |
| `implementation/pipeline/market_events.json` | 516 | 27 | `80b88035524102f6…` | production — data: FOMC/CPI calendar used to tag tape records |
| `implementation/pipeline/maxpain_log.py` | 24614 | 495 | `0b34acc40b3c520f…` | production — 5-min logger; JSONL + tape.db mirror (J1-line behavior, 50/50 suite) |
| `implementation/pipeline/maxpain_milestones.py` | 2278 | 82 | `3f5ac1fab27247f1…` | production — helper: 5/30-day milestone lead/lag checks |
| `implementation/pipeline/ranges_today.py` | 3895 | 104 | `f510043718fa8d81…` | production — helper: intraday ranges for EOD note/dashboard |
| `implementation/pipeline/run_interpreter.sh` | 1857 | 49 | `0ed2724bef0cd05d…` | production — supervisor (restarts interpreter ~5s, logs exits) |
| `implementation/pipeline/schwab_client.py` | 6424 | 185 | `cc6a3022633ed678…` | OPTIONAL / UNAVAILABLE — Schwab OAuth + chain probe scaffold; no approved app, no keys; NOT wired into the interpreter |
| `implementation/pipeline/state_alerts.py` | 8677 | 207 | `e7320853589746c1…` | production — loaded-gun state + charm trigger |
| `implementation/pipeline/tape_db.py` | 41975 | 965 | `9031b67d59b7e05c…` | production — tape.db schema/migrations + mirror/replay logic |
| `implementation/pipeline/test_data_keys.py` | 6438 | 164 | `8dc17fb2fcd3ed8a…` | OPTIONAL — dev utility probing Tradier/Massive keys from env vars; no keys present; not part of the running stack |
| `implementation/pipeline/test_watcher_windows.py` | 3258 | 87 | `d8207913c0c852d3…` | regression tests — 12 synthetic checks for watcher displacement windows + wall_break |
| `implementation/pipeline/tests/j1_replay_tests.py` | 31361 | 782 | `244aca93e9c568d6…` | regression suite — 50 tests (J1..J1-F lines) against maxpain_log.py + tape_db.py |
| `implementation/pipeline/wall_tests.py` | 10750 | 277 | `e1958ea54a70de88…` | production — catalytic early detection: wall-test grading (added 2026-10-15) |
| `implementation/pipeline/watcher.py` | 11613 | 281 | `3a712d0adafcb699…` | production — alert watcher (maxpain/walls/flip/pin/spot_move/wall_break) |

