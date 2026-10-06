# LIVE-G1 Investigation: Hosted Page Replacement Timeline

## The Hosted URL
https://muse.ai/s/0dte-dashboard-xlk6gxicxxxtxwxnxp
Artifact slug: 0dte-dashboard
Goal: 0dte-tape-alert-watch (goal_e97a113213f6)

## Original State (2026-10-02 through 2026-10-05 ~16:39 PDT)
The page served the **0DTE trading dashboard**: real intraday SPY options tape data
including spot, max pain, pin score, expected move, gamma flip/walls, hedge pressure,
GEX heatmap, event pills. Data from dashboard_data.json built from the live
interpreter feed (237 records for Oct 5 session).

## The Replacement (2026-10-05 ~16:39 PDT)
User said "update the hosted site". The artifact.edit with verbatim_request
"update the hosted site" was interpreted by the builder as serving the **GEX
granular dashboard** (the UI-G3 synthetic fixture explorer) instead of the
0DTE trading dashboard.

The page then served synthetic fixture content: scenario controls, precomputed
spots, expiry-level call/put OI exposure, strike drilldowns — all from the
UI-G3 synthetic fixture (fixtures/gex-granular-v1/), NOT live trading data.

## User Report (2026-10-05 ~17:04 PDT)
User: "what i don’t want that served as the main site"

## The Restoration (2026-10-05 ~17:04-17:09 PDT)
Immediate artifact.edit to restore the 0DTE trading dashboard with explicit
instruction that the GEX dashboard is a separate red-team deliverable.
Rebuilt and shared. Public link now serves the 0DTE trading dashboard again.

## Verification Status
- Replacement: CONFIRMED (user observed it, builder handoff confirmed it)
- Restoration: CONFIRMED (builder handoff confirms 0DTE dashboard restored,
  GEX fixture no longer served at main URL)
- Current state: Main URL serves 0DTE trading dashboard with Oct 5 session data

## LIVE-G1 Requirements Going Forward
1. The synthetic GEX demo must live on a SEPARATE clearly labeled route,
   never replacing the main 0DTE dashboard.
2. Any future "update the hosted site" must be scoped explicitly to which
   dashboard is intended.
3. The 0DTE dashboard needs a versioned read-only adapter with real source
   identities (not fixture substitution).
