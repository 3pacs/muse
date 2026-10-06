# LIVE-G1: Hosted URL to Source/Build/Data Mapping

## Hosted URL
https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp

## Artifact Identity
- Slug: 0dte-dashboard
- Kind: web_static (hosted web page)
- Goal: 0dte-tape-alert-watch (goal_e97a113213f6)
- Share type: cloudflare
- Public URL stable across rebuilds (same URL serves latest shared build)

## Source: Backend Data Pipeline
- **Interpreter**: ~/workspace/stepdad-0dte/interpreter.py (port 8787)
  - Polls gex.stepdad.finance RTD feed + Nasdaq wide-chain wings
  - Computes: max pain, gamma walls/flip/regime, pin score, expected move,
    hedge buckets, charm/vanna, IV metrics
  - Endpoints: /feed/gamma, /feed/flow, /feed/vanna-charm, /feed/iv,
    /feed/all, /feed/maxpain, /feed/positioning, /stream
- **Logger**: ~/workspace/stepdad-0dte/maxpain_log.py (cron every 5m)
  - Appends to: ~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_history.jsonl
  - Mirrors to: ~/workspace/goals/0dte-tape-alert-watch/hidden_files/tape.db (SQLite)
  - Backend source pin: 8649ad54 (J1-F P1, accepted)
- **Dashboard builder**: ~/workspace/stepdad-0dte/dashboard_build.py
  - Reads: maxpain_history.jsonl + gex_history.jsonl
  - Writes: ~/workspace/goals/0dte-tape-alert-watch/hidden_files/dashboard_data.json
  - Current: 237 records (Oct 5 session), 60 heatmap cols

## Build: Artifact Builder
- Builder: web_artifact_builder (static)
- Input: dashboard_data.json (embedded at build time)
- Output: static HTML/CSS/JS page
- Data freshness: fixed at build time (no live fetch on page open)
- Last build: 2026-10-05 ~17:07 PDT (restoration build)
- Last share: 2026-10-05 ~17:09 PDT

## Data Endpoints (for adapter design)
The LIVE-G1 adapter must expose:
- `GET /adapter/status` — backend health, last poll time, data vintage
- `GET /adapter/snapshot` — latest full tape record with per-field clocks
- `GET /adapter/history?limit=N` — recent records for ranges table
- `GET /adapter/heatmap` — GEX strike×time data

Each field carries:
- `value`: the datum
- `source`: which feed/endpoint produced it (e.g., "gex.stepdad.finance RTD", "nasdaq wide-chain")
- `source_at`: when the source produced it (source clock)
- `received_at`: when our interpreter received it (receipt clock)
- `vintage`: for OI — which day's settlement (OI is T+1)
- `stale`: boolean, true if older than threshold
- `unavailable`: boolean, true if source failed

## Route Separation
- Main: https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp → 0DTE trading dashboard (REAL data)
- Synthetic GEX demo: SEPARATE route, clearly labeled "Synthetic Fixture — Not Market Data"
  - Currently: standalone file at ~/workspace/uig1/frontend/gex-granular-dashboard.html
  - Must NEVER replace the main URL
