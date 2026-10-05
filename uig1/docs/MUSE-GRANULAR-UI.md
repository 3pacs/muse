# UI-G1 — Granular GEX Fixture Dashboard

## Scope

Frontend/UI fixture and test files only. No J1 backend files (`maxpain_log.py`, `tape_db.py`) or shared GRID code modified. No interpreter or dashboard_build changes. Fixture-first lane; math/live integration waits for GRID final schema.

## Source

- GRID origin: `ad2330886ce8f97758bd4c599fbfc731adc1d742`
- Contract: `docs/GEX-GRANULAR-V1-GRID-CONTRACT.md` (byte-exact, SHA-256 `605bf83c...`)
- Input: `docs/fixtures/gex-granular-v1.input.json` (SHA-256 `f979e97e...`)
- Result: `docs/fixtures/gex-granular-v1.result.json` (SHA-256 `70b10bbb...`)
- All consumed verbatim; no duplicate estimator.

## Files

- `frontend/gex-granular-dashboard.html` — standalone dashboard, result JSON embedded
- `fixtures/gex-granular-v1/` — contract.md, input.json, result.json (byte-exact copies)
- `tests/ui/test_dashboard.py` — 30 offline tests (21 UI-G1 + 9 UI-G2)
- `docs/MUSE-GRANULAR-UI.md` — this file
- `build_receipt.json` — immutable build provenance (hashes, not runtime clock)

## UI-G2 Changes (2026-10-05)

Addresses the 8 failed browser contracts:

1. **source_authentication axis**: Status cards now show all four axes including Source Auth (SYNTHETIC).
2. **Valuation/spot clocks**: Valuation timestamp and spot source/receipt clocks rendered in context bar.
3. **Spot selector**: All precomputed spots (760/765/770) selectable; no hardcoded spots[0].
4. **Contract provenance**: Per-contract quote/Greek/OI source and receipt clocks, OI vintage (unknown flagged), provider gamma numeric value with NOT_FRESH label, unknown flags, IV origin.
5. **Keyboard accessible**: Expiry rows have tabindex=0, role, aria-expanded, Enter/Space handlers.
6. **Responsive**: Viewport overflow hidden, tables in scroll regions, mobile CSS at 480px.
7. **Build provenance**: Immutable SHA-256 hashes in BUILD object; no `new Date()` runtime clock.
8. **Null aggregates**: Null aggregates render explicit unavailable state, no exception, no zero substitution.

## Verification

30/30 UI tests pass. No network calls, no Greek recomputation, no live adapter.
Open via `python3 -m http.server` in `uig1/frontend/`. No deployment; standalone artifact for review.
