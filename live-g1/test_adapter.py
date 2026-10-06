#!/usr/bin/env python3
"""
LIVE-G1 adapter tests — realistic captured-response tests.

Tests the adapter against real backend data (tape.db, journal).
No fixtures, no synthetic data. If backend is unavailable, tests
verify the adapter reports unavailable honestly.
"""

import json
import subprocess
import sys
from pathlib import Path

ADAPTER = Path(__file__).parent / "live_g1_adapter.py"

results = []

def record(name, ok, observed=""):
    results.append((name, bool(ok), observed))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  :: {observed}"))

def run_adapter(cmd, *args):
    r = subprocess.run(
        [sys.executable, str(ADAPTER), cmd, *args],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(r.stdout) if r.returncode == 0 else None

# --- Status endpoint ---
status = run_adapter("status")
record("status_returns", status is not None)
if status:
    record("status_has_adapter_version", status.get("adapter_version") == "live-g1/v1")
    record("status_has_backend_pin", status.get("backend_pin") == "8649ad54")
    record("status_has_backend_section", "backend" in status)
    record("status_has_vintage", "data_vintage" in status)
    # Interpreter should be reachable (it's running on :8787)
    interp = status.get("backend", {}).get("interpreter", {})
    record("status_interpreter_reachable", interp.get("reachable") is True,
           f"reachable={interp.get('reachable')}")
    # Tape DB should have snapshots
    db = status.get("backend", {}).get("tape_db", {})
    record("status_db_has_snapshots", db.get("snapshot_count", 0) > 0,
           f"count={db.get('snapshot_count')}")
    # Vintage honesty: market is closed now (after hours), should be stale
    vintage = status.get("data_vintage", {})
    record("status_vintage_honest", vintage.get("stale") is True,
           f"stale={vintage.get('stale')}, reason={vintage.get('stale_reason')}")

# --- Snapshot endpoint ---
snap = run_adapter("snapshot")
record("snapshot_returns", snap is not None)
if snap and "fields" in snap:
    fields = snap["fields"]
    record("snapshot_has_spot", "spot" in fields)
    record("snapshot_has_max_pain", "max_pain" in fields)
    # Every field must have provenance
    for fname, fval in fields.items():
        has_prov = all(k in fval for k in ("value", "unit", "source", "source_at", "stale", "unavailable"))
        record(f"snapshot_field_{fname}_has_provenance", has_prov)
        # No fixture substitution: unavailable fields must have value=None
        if fval.get("unavailable"):
            record(f"snapshot_field_{fname}_unavailable_honest", fval.get("value") is None)
    # OI fields must have vintage
    for oi_field in ("call_oi", "put_oi"):
        if oi_field in fields:
            record(f"snapshot_{oi_field}_has_vintage", "oi_vintage" in fields[oi_field])
    # Spot must be a realistic SPY value (not a fixture like 100.0)
    spot_val = fields.get("spot", {}).get("value")
    record("snapshot_spot_realistic", spot_val is not None and 700 < spot_val < 900,
           f"spot={spot_val}")

# --- History endpoint ---
hist = run_adapter("history", "--limit", "10")
record("history_returns", hist is not None)
if hist:
    record("history_has_records", len(hist.get("records", [])) > 0)
    record("history_respects_limit", len(hist.get("records", [])) <= 10)
    if hist.get("records"):
        rec = hist["records"][0]
        record("history_record_has_ts", "recorded_at" in rec)
        record("history_record_has_spot", "spot" in rec)

# --- Heatmap endpoint ---
hm = run_adapter("heatmap")
record("heatmap_returns", hm is not None)
if hm:
    # May have cells or error if file missing; either way must be honest
    has_cells = "cells" in hm
    has_error = "error" in hm
    record("heatmap_honest", has_cells or has_error)

# --- Summary ---
failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} pass")
sys.exit(1 if failed else 0)
