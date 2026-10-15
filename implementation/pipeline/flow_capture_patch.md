# Flow capture patch — PREPARED, NOT APPLIED (2026-10-13)

## Why
The free flow proxy discussed in chat on 2026-10-13 (per-strike Δvolume rate,
premium $, vol/OI flags — to test whether flow precedes max-pain repricing at
the 30-day milestone) needs per-strike volume history. Verified 2026-10-13
~17:08 UTC against the live system:

- `tape.db` stores only aggregate call/put volume + one `top_unusual` strike
  per 5-min record. `gex_history.jsonl` stores per-strike GEX only, no volume.
- `maxpain_log.py` already receives the full `elevated_volume_activity` list
  from `/feed/flow` every run (line 66: `unusual = f.get("elevated_volume_activity")`)
  — 12 entries in the live sample checked — but persists only `unusual[0]`
  (lines 114–117) plus a count and summed notional. The rest is discarded.
- Per-strike intraday volume cannot be reconstructed later. Every session
  without capture is permanently lost data; CPI day Wed Oct 14 is the
  highest-value session to start capturing.

So the in-chat statement that the proxy could be "backfilled from tape.db"
is not correct for per-strike volume — capture has to start now, forward-only.

## Patch (maxpain_log.py, append-only, mirrors the gex_history pattern)

1. Add a path constant near line 27 (after GEX_SNAP_PATH):

```python
FLOW_SNAP_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/flow_history.jsonl")
```

2. In the brand-new-event branch (where `_append_line(GEX_SNAP_PATH, gex_dict)`
   runs), add after it:

```python
            flow_dict = {"ts": rec["ts"], "expiry": rec["expiry"],
                         "spot": spot,
                         "elevated": [{"strike": u.get("strike"),
                                       "side": u.get("side"),
                                       "volume": u.get("volume"),
                                       "oi": u.get("oi"),
                                       "vol_oi": u.get("vol_oi"),
                                       "notional_k": u.get("notional_k"),
                                       "src": u.get("src")} for u in unusual],
                         "top_volume": [{"strike": t.get("strike"),
                                         "call_vol": t.get("call_vol"),
                                         "put_vol": t.get("put_vol")}
                                        for t in top_vol]}
            _append_line(FLOW_SNAP_PATH, flow_dict)
```

Notes for whoever applies it:
- `spot`, `unusual`, `top_vol` are already in scope in `main()`.
- Same identity discipline as the GEX snap: write only for brand-new accepted
  events, never on the converge/repair path (accepted-event content only).
- No schema change to `maxpain_history.jsonl` or `tape.db`; existing consumers
  are untouched. New file is additive and can be deleted with zero impact.
- After applying: restart nothing (cron runs the script fresh every 5 min);
  verify one new line lands in `flow_history.jsonl` on the next logger run and
  that `maxpain_history.jsonl` records are unchanged in shape.

## What this enables
After ~1 session of capture: per-strike Δvolume between 5-min snapshots,
premium-weighted flow (volume is stored alongside the feed's `notional_k`),
and vol/OI flag history — the three free gauges named in the 2026-10-13 chat —
testable at the 30-day milestone against actual next-morning OI changes.
