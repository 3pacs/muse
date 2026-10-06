# LIVE-G1-DELIVERY: Route Mapping

## Primary Route (REAL data)
- **URL**: https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp
- **Artifact**: `0dte-dashboard` (web_static)
- **Content**: 0DTE trading dashboard — spot, max pain, gamma flip/walls,
  pin score, session ranges, hedge pressure, GEX heatmap
- **Data source**: `dashboard_data.json` (237 records, Oct 5 session),
  embedded at build time
- **Adapter**: `live-g1/v1` (`live-g1/live_g1_adapter.py`, backend pin `8649ad54`)
- **Status**: DEPLOYED and serving (verified via builder handoff 2026-10-05)

## Demo Route (SYNTHETIC, clearly labeled)
- **Artifact**: `gex-synthetic-fixture-demo` (web_static, NOT shared)
- **Content**: GEX Synthetic Fixture Demo — scenario controls, precomputed
  spots, expiry-level OI exposure, strike drilldowns
- **Label**: "Synthetic Fixture — Not Market Data" (prominent header)
- **Data source**: `fixtures/gex-granular-v1/` (synthetic, UI-G3)
- **Status**: BUILT but NOT published (no public URL; Anik has not requested it)
- **Guarantee**: Never replaces the primary route

## Transport
The primary dashboard UI exposes `window.LIVE_G1`:
- `LIVE_G1.transport.base` — set to adapter URL for live refresh (default: null = embedded)
- `LIVE_G1.refresh()` — async controller: fetches status/snapshot/history,
  keeps last-good on failure, ignores non-newer snapshots, surfaces errors honestly
- `LIVE_G1.fetchStatus()`, `fetchSnapshot()`, `fetchHistory(n)` — pure getters

Current deployment uses **embedded build-time data** (static artifact).
For live refresh, run the read-only service and set the transport base:

```bash
cd ~/workspace/live-g1/delivery
python3 serve_adapter.py --port 8899   # read-only, localhost only
# in page console:
LIVE_G1.transport.base = "http://127.0.0.1:8899/adapter/v1";
LIVE_G1.refresh();
```

Service endpoints: `/adapter/v1/status`, `/adapter/v1/snapshot`,
`/adapter/v1/history?limit=N`, `/adapter/v1/heatmap?limit=N`.
Read-only; no writes, no mutations.

**Source distinction**: the local API (`serve_adapter.py` on localhost) serves
live adapter output. The owner-described hosted source (the `0dte-dashboard`
artifact URL above) is a separate builder-generated page. They are distinct
sources until the artifact is replaced with this delivery's HTML.

## Build Reproducibility
```bash
cd ~/workspace/live-g1/delivery
python3 ../live_g1_adapter.py status > captures/status.json
python3 ../live_g1_adapter.py snapshot > captures/snapshot.json
python3 ../live_g1_adapter.py history --limit 20 > captures/history.json
python3 build.py  # embeds captures into template.html
# Output: 0dte-dashboard-live-g1.html (sha256 in BUILD_RECEIPT.json)
```
