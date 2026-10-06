# LIVE-G1 Adapter Specification v1

## Purpose
Versioned read-only adapter over the 0DTE backend (source pin 8649ad54).
Exposes real tape data with full provenance. Never substitutes fixture values.

## Version
`live-g1/v1`

## Endpoints

### GET /adapter/v1/status
Backend health and data vintage.

```json
{
  "adapter_version": "live-g1/v1",
  "backend_pin": "8649ad54",
  "backend": {
    "interpreter": {"reachable": true, "last_poll_at": "2026-10-05T23:59:00Z"},
    "tape_db": {"path": ".../tape.db", "snapshot_count": 385, "latest_at": "..."},
    "journal": {"path": ".../maxpain_history.jsonl", "record_count": 237}
  },
  "data_vintage": {
    "latest_record_at": "2026-10-05T20:00:00Z",
    "market_hours": false,
    "stale": true,
    "stale_reason": "market closed; last record from session close"
  }
}
```

### GET /adapter/v1/snapshot
Latest full tape record with per-field provenance.

Each field:
```json
{
  "spot": {
    "value": 776.21,
    "unit": "USD",
    "source": "gex.stepdad.finance RTD",
    "source_at": "2026-10-05T19:59:45Z",
    "received_at": "2026-10-05T19:59:50Z",
    "stale": false,
    "unavailable": false
  },
  "max_pain": {
    "value": 768.0,
    "unit": "USD",
    "source": "computed from OI (nasdaq wide-chain wings)",
    "source_at": "2026-10-05T19:59:50Z",
    "received_at": "2026-10-05T19:59:50Z",
    "oi_vintage": "2026-10-04 settlement (T+1)",
    "stale": false,
    "unavailable": false
  }
}
```

Fields: spot, max_pain, gamma_flip, call_wall, put_wall, pin_score,
expected_move, regime, charm, vanna, call_oi, put_oi, iv_atm, etc.

### GET /adapter/v1/history?limit=50
Recent records for ranges table. Each record has `recorded_at` (UTC).

### GET /adapter/v1/heatmap
GEX strike×time data with formula tags.

## Honesty Rules
1. If interpreter unreachable: `backend.interpreter.reachable=false`,
   serve last known data with `stale=true` and reason.
2. If a field's source failed: `unavailable=true`, `value=null`,
   never invent a number.
3. OI fields always carry `oi_vintage` (T+1 settlement date).
4. Market closed: `market_hours=false`, data marked stale with reason.
5. NEVER return fixture/synthetic values. If no real data, return
   `unavailable=true`.
6. Clocks: `source_at` is when the source produced it; `received_at`
   is when we received it. Both in UTC ISO-8601.

## What This Is NOT
- Not a live trading feed (data is 5-min snapshots, embedded at build)
- Not a prediction (see literature survey: no directional edge)
- Not connected to any broker (no orders, no funds movement)
