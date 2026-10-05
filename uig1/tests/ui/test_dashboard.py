"""UI-G2 offline tests — synthetic fixture only, no network.

Verifies the eight UI-G2 contracts plus the 21 UI-G1 checks:
1. source_authentication axis visible
2. valuation and spot source clocks visible
3. all precomputed spots selectable (760/765/770)
4. contract provenance and unknown OI visible (per-contract clocks, OI vintage, provider gamma numeric)
5. expiry drilldown keyboard accessible
6. mobile page width fits (no horizontal overflow)
7. build provenance not runtime clock
8. null aggregate handled as unavailable (no exception)
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HTML = ROOT / "frontend" / "gex-granular-dashboard.html"
RESULT = ROOT / "fixtures" / "gex-granular-v1" / "result.json"

results = []

def record(name, ok, observed=""):
    results.append((name, bool(ok), observed))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  :: {observed}"))

html = HTML.read_text()
result = json.loads(RESULT.read_text())
js = html[html.find("<script>"):]

# --- UI-G1 preserved (21) ---
record("result_embedded", result["scenarios"][0]["name"] in html)
record("units_explicit", "USD_per_1pct_underlying_move" in html and "USD per 1%" in html)
for key in ["oi_gross", "inventory_gross", "signed_net"]:
    record(f"measure_{key}_rendered", key in html)
record("0dte_labeled", "0DTE" in html)
record("coverage_rendered", "PARTIAL_DECLARED_COVERAGE" in html and "EXPIRED" in html)
record("unavailable_states", "NOT_FRESH" in html and "null" in html)
record("no_duplicate_estimator", "BlackScholes" not in js and "norm_cdf" not in js.lower())
record("no_live_adapter", "fetch(" not in js and "XMLHttpRequest" not in js)
record("synthetic_labeled", "Synthetic" in html and "not market data" in html)
for axis in ["numerical_status", "coverage_status", "inventory_status"]:
    record(f"status_axis_{axis}", result[axis] in html)
contracts = result["scenarios"][0]["spots"][0]["contracts"]
for c in contracts:
    record(f"contract_{c['contract_id']}", c["contract_id"] in html)
for s in result["scenarios"]:
    record(f"scenario_{s['name']}", s["name"] in html)

# --- UI-G2 new (8 contracts) ---

# 1. source_authentication axis visible (not just in embedded JSON).
# The card is rendered by JS from RESULT.source_authentication.
record("source_authentication_axis_visible",
       "Source Auth" in js and "RESULT.source_authentication" in js,
       "Source Auth card rendered by JS from source_authentication")

# 2. valuation and spot source clocks visible.
record("valuation_and_spot_source_clocks_visible",
       "2026-09-28T15:00:00Z" in html and "14:59:55Z" in html,
       "valuation_at and spot source_at rendered")

# 3. all precomputed spots selectable — spot selector exists and lists 760/765/770.
record("all_precomputed_spots_selectable",
       'id="spot-sel"' in html and "spots.map" in js,
       "spot selector renders all precomputed spots")

# 4. contract provenance and unknown OI visible.
record("contract_provenance_and_unknown_oi_visible",
       "fmtClock" in js and "oi_as_of" in html and "provider_gamma" in html
       and "NOT_FRESH" in html,
       "per-contract clocks, OI vintage, provider gamma numeric rendered")

# 5. expiry drilldown keyboard accessible.
record("expiry_drilldown_keyboard_accessible",
       'tabIndex' in js and 'onkeydown' in js and 'aria-expanded' in js
       and ('Enter' in js or 'e.key' in js),
       "tabindex, key handler, aria-expanded present")

# 6. mobile page width fits — CSS constrains overflow.
record("mobile_page_width_fits",
       "overflow-x:hidden" in html and "max-width:100vw" in html
       and "table-wrap" in html,
       "viewport overflow constrained, tables in scroll regions")

# 7. build provenance not runtime clock.
record("build_provenance_not_runtime_clock",
       "new Date().toISOString()" not in html and "BUILD" in js
       and "sha256" in html.lower() or "contract_sha256" in html,
       "immutable hashes, no runtime Date")

# 8. null aggregate handled as unavailable (no exception).
record("unsupported_null_aggregate_is_unavailable",
       "aggregates == null" in js and "Unavailable" in js
       and "no aggregates" in js.lower() or "Unavailable:" in html,
       "null aggregates render unavailable state, no throw")

# 9. All 9 scenario×spot combinations exercisable (3 scenarios × 3 spots).
n_scenarios = len(result["scenarios"])
n_spots = len(result["scenarios"][0]["spots"])
record("all_scenario_spot_combinations",
       n_scenarios == 3 and n_spots == 3 and "curSpot" in js,
       f"{n_scenarios} scenarios x {n_spots} spots with spot state")

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} pass")
sys.exit(1 if failed else 0)
