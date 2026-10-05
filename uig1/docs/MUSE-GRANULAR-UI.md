# UI-G1 — Granular GEX Fixture Dashboard

## Scope

Frontend/UI fixture and test files only. No J1 backend files (`maxpain_log.py`, `tape_db.py`) or shared GRID code modified. No interpreter or dashboard_build changes. Fixture-first lane; math/live integration waits for GRID final schema.

## Source

- GRID origin: `ad2330886ce8f97758bd4c599fbfc731adc1d742`
- Contract: `docs/GEX-GRANULAR-V1-GRID-CONTRACT.md` (byte-exact)
- Input: `docs/fixtures/gex-granular-v1.input.json`
- Result: `docs/fixtures/gex-granular-v1.result.json`
- All consumed verbatim; no duplicate estimator.

## Files

- `frontend/gex-granular-dashboard.html` — standalone dashboard, result JSON embedded
- `fixtures/gex-granular-v1/` — contract.md, input.json, result.json (byte-exact copies)
- `tests/ui/test_dashboard.py` — 21 offline tests
- `docs/MUSE-GRANULAR-UI.md` — this file

## Features

- Scenario selector (3 scenarios: oi_sign_baseline, all_short, partial_neutral)
- Strike × expiry drilldown (click expiry row)
- 0DTE labeling (UTC-date matching only)
- Call/put breakdown
- oi_gross vs inventory_gross vs signed_net (USD per 1% underlying move)
- Coverage status with exclusions
- Null/unavailable states preserved (oi_as_of null, NOT_FRESH provider gamma)
- All five disclaimers rendered
- Four status axes: numerical, coverage, inventory, units

## Verification

21/21 UI tests pass. No network calls, no Greek recomputation, no live adapter.
