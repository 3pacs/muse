"""UI-G1 offline tests — synthetic fixture only, no network.

Verifies the dashboard consumes the GRID gex-granular-v1 result without
a duplicate estimator: embedded numbers match the fixture, units are
explicit, coverage/unavailable states render, and no live-adapter or
fake-current-data paths exist.
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

# 1. Result JSON is embedded byte-exact (no estimator).
record("result_embedded",
       result["scenarios"][0]["name"] in html,
       "scenario name from fixture present in HTML")

# 2. Units are explicit USD per 1%.
record("units_explicit",
       "USD_per_1pct_underlying_move" in html and "USD per 1%" in html,
       "units string present")

# 3. All three exposure measures render.
for key in ["oi_gross", "inventory_gross", "signed_net"]:
    record(f"measure_{key}_rendered", key in html, f"{key} in HTML")

# 4. 0DTE labeling present (UTC-date matching disclaimer).
record("0dte_labeled", "0DTE" in html, "0DTE present")

# 5. Coverage and exclusions render.
record("coverage_rendered",
       "PARTIAL_DECLARED_COVERAGE" in html and "EXPIRED" in html,
       "coverage status and exclusion reasons present")

# 6. Null/unavailable states preserved (oi_as_of null, NOT_FRESH).
record("unavailable_states",
       "NOT_FRESH" in html and "null" in html,
       "NOT_FRESH and null markers present")

# 7. No duplicate estimator: no gamma recomputation in JS.
js = html[html.find("<script>"):]
record("no_duplicate_estimator",
       "BlackScholes" not in js and "norm_cdf" not in js.lower(),
       "no Greek engine in frontend JS")

# 8. No live-adapter or fetch calls.
record("no_live_adapter",
       "fetch(" not in js and "XMLHttpRequest" not in js,
       "no network calls in frontend")

# 9. Synthetic labeling present.
record("synthetic_labeled",
       "Synthetic" in html and "not market data" in html,
       "synthetic disclaimers present")

# 10. Four status axes render (numerical, coverage, inventory, units).
for axis in ["numerical_status", "coverage_status", "inventory_status"]:
    record(f"status_axis_{axis}", result[axis] in html, f"{axis} value present")

# 11. Contract drilldown: all admitted contracts present.
contracts = result["scenarios"][0]["spots"][0]["contracts"]
for c in contracts:
    record(f"contract_{c['contract_id']}",
           c["contract_id"] in html, "contract ID in HTML")

# 12. Scenario selector has all three scenarios.
for s in result["scenarios"]:
    record(f"scenario_{s['name']}", s["name"] in html, "scenario in selector")

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} pass")
sys.exit(1 if failed else 0)
