# Synthetic fixtures

**Every value in this folder is invented** (spot 500.25, walls 505/495,
dates in January 2026). The *structure* is exact: it mirrors the live
`/feed/all` and `/feed/signals` payloads as served by
`pipeline/interpreter.py` on 2026-10-15. Each JSON fixture carries
top-level `"_synthetic": true` and `"_fixture"` keys so no consumer can
mistake it for market data.

| File | Case |
|---|---|
| `feed_all_success.json` | `/feed/all` success, market open. `gamma.by_strike` is truncated to 2 of 151 rows (noted in-band); every other section is complete. |
| `feed_all_last_session.json` | Same payload with `market_open: false` — the post-close state, where the feed keeps serving the finished session. |
| `feed_all_error.json` | The spot=0 error (Sunday-evening / pre-open: next chain published, no quote yet). Exact error shape from `build_snapshot()`; the logger treats non-`ok` status as FEED_ERROR and skips the record. |
| `feed_signals_success.json` | `/feed/signals` with the loaded gun ACTIVE, one charm trigger, two stacks, and a fully-tagged `vol_ignition` print (mega/cluster/prints_60m/at_lows present). |
| `feed_signals_legacy_tags.json` | **Missing legacy tags case:** `vol_ignition` rows stored before the 2026-10-14 print enrichment carry only `{vol, mult}` in `detail`. The mega/cluster/prints_60m/at_lows keys are *absent, not null*. Consumers must treat missing tags as unknown, never as false. |
| `feed_signals_error.json` | `/feed/signals` failure shape: the endpoint is failure-proof (error payload, HTTP 200, never an exception) so a tape.db problem can never take the feed down. |
| `feed_signals_cluster_true.json` | Added for ADOPT-B1 (2026-10-15): same shape as `feed_signals_success.json`, but the `vol_ignition` print is fully tagged with `cluster: true, prints_60m: 3` — the clustering state for the fixture-preview set (success covers explicit-false/isolated, legacy covers missing/unknown). |
| `sse_stream_sample.txt` | `/stream` SSE frames plus the reconnect/replay contract: no event ids, no replay buffer, 30 s full-snapshot frames; reconnecting clients get the current snapshot on the next tick. |
