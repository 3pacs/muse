# LIVE-G1 Delivery: Hosted Build Integration

## Investigation Summary

**Replacement verified**: On 2026-10-05 ~16:39 PDT, the hosted 0DTE dashboard
at https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp was replaced by the
GEX synthetic fixture explorer (UI-G3) due to an ambiguous "update the hosted
site" instruction. The user reported it at ~17:04 PDT ("what i don't want that
served as the main site"). Restoration completed ~17:09 PDT. The main URL now
serves the 0DTE trading dashboard with Oct 5 session data (237 records).

## Route Map

| Route | Content | Data Source |
|-------|---------|-------------|
| https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp | 0DTE trading dashboard (REAL) | dashboard_data.json (237 records, Oct 5) |
| (new) gex-synthetic-fixture-demo | GEX fixture explorer (SYNTHETIC) | fixtures/gex-granular-v1/ |

The synthetic demo is on a SEPARATE clearly labeled route. It NEVER replaces
the main URL.

## Adapter: live-g1/v1

**Location**: `~/workspace/live-g1/live_g1_adapter.py`
**Backend pin**: 8649ad54 (J1-F P1, accepted)
**Tests**: 33/33 pass (`test_adapter.py`)

### Endpoints
- `status` — backend health, data vintage, market hours, stale reasons
- `snapshot` — latest record with per-field provenance (value, unit, source,
  source_at, received_at, stale, unavailable, oi_vintage for OI fields)
- `history --limit N` — recent records
- `heatmap` — GEX strike×time with formula tags

### Honesty Guarantees
1. Unavailable fields return `value=null, unavailable=true` — never invented.
2. OI fields carry `oi_vintage` (T+1 settlement).
3. Market closed → `stale=true` with explicit reason.
4. No fixture values ever substituted for live data.

## Build/Schema/Endpoint/Freshness Mapping

| Component | Identity |
|-----------|----------|
| Backend source | 3pacs/muse @ 8649ad54 (J1-F P1) |
| UI source | 3pacs/muse @ e5a8a0ce (UI-G3 accepted) |
| Adapter version | live-g1/v1 |
| Data file | dashboard_data.json (237 records, 60 heatmap cols) |
| Tape DB | tape.db (617 snapshots) |
| Journal | maxpain_history.jsonl (617 records) |
| Interpreter | localhost:8787 (reachable) |
| Data freshness | Fixed at build time (static artifact, no live fetch) |
| Last build | 2026-10-05 ~17:07 PDT |
| Last share | 2026-10-05 ~17:09 PDT |

## Deployment States

- **Code-ready**: YES — adapter implemented, 33/33 tests pass
- **Deployment-ready**: YES — artifact builds succeed, routes separated
- **Deployed**: YES — public URL serves 0DTE dashboard (verified via builder)

## Blockers
None. No credentials, purchases, or trading authorization needed for this
read-only integration task.

## What Was NOT Done
- No live data feed (artifact is static; data embedded at build)
- No broker connection (read-only; no orders)
- No predictions (literature: no directional edge from these variables)
