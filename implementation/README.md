# 0DTE implementation source — intake package (2026-10-15)

Implementation source for the Oct 15 self-host handoff
(`docs/0DTE-SELF-HOST-HANDOFF.md`, commit `4ce50f57`, which was
documentation only). This package is the code the handoff describes,
published for offline adoption review per the request on PR #2
(comment 6202190663).

## Contents

- `pipeline/` — the production stack, exactly as running on
  2026-10-15: interpreter + supervisor, watcher, logger + tape.db,
  indicator engine, state alerts, wall-test scorer, dashboard data
  builder, helpers, regression tests, and two explicitly-marked
  optional components (Schwab scaffold, key-probe utility).
- `dashboard-streaming/` — source of the production streaming
  dashboard (Muse artifact, slug `0dte-streaming-dashboard`):
  React client, server actions, drizzle migrations. Excludes
  `node_modules/`, build output, and the runtime database.
  Build/run is via the Muse artifact platform (`client/build.mjs`);
  for self-hosting, the handoff doc remains the specification and
  this source is the reference implementation.
- `fixtures/` — clearly labeled **synthetic** fixtures for
  `/feed/all`, `/feed/signals`, and the SSE stream: success, error,
  last-session, missing-legacy-tags, and reconnect/replay cases.
- `MANIFEST.md` / `SHA256SUMS.txt` — per-file manifest with SHA-256
  for every file (the two manifest files themselves are anchored by
  the commit, not self-hashed).
- `LINEAGE.md` — lineage against reviewed pin `6ffff8ab`: the
  reviewed delivery line was never merged; this stack descends from
  main `43c2cd41` and evolved in production. Details and diff counts
  inside.
- `PROVENANCE.md` — ownership/license, data sources and clocks,
  units and formula versions, DDL/migrations, JSONL schemas,
  replay/dedup behavior.
- `TESTS.md` — exact-source test commands and results
  (50/50 J1 suite, 12/12 watcher checks, all modules compile).

## Exclusions (deliberate)

Runtime state and data (`watcher_state.json`, `tape.db`, the JSONL
archives, the dashboard's `app.db`), caches, and build artifacts are
not source and are not included; their schemas are documented in
PROVENANCE.md. No credentials exist in this tree — the optional
components read keys from environment variables, and none are set in
the production environment for them.

## Status

Source/fixture intake for offline review. Nothing here is a
deployment: the production system continues to run in its own
workspace, and the self-host cutover remains governed by the handoff
document and the owner's decisions recorded there.
