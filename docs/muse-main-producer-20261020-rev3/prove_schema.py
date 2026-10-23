#!/usr/bin/env python3
"""Offline contract checks for the rev3 /feed/all schema (producer pin b95d1c3c…).

Validates: meta-schema validity; the retained captured ok envelope; labeled
SYNTHETIC source-derived fixtures for the sparse-timeout, no-quote,
quarantined and starting shapes (shapes taken from the pinned source text —
these are NOT market captures); numeric/null wall admission; unknown-status
rejection. Emits a receipt JSON beside this script. No network, no producer
import: fixtures are hand-built literals matching the pinned source's return
statements.
"""
import json, hashlib, copy, sys, os
from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    with open(os.path.join(HERE, n), "rb") as f:
        raw = f.read()
    return raw, json.loads(raw)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

schema_raw, schema = load("feed_all.schema.json")
cap_raw, capture = load("envelope-ok-afterclose-20261020.json")

checks = []
def record(name, passed, detail):
    checks.append({"check": name, "pass": bool(passed), "detail": detail})

# 1. meta-schema validity
try:
    Draft202012Validator.check_schema(schema)
    record("meta_schema_valid", True, "Draft202012Validator.check_schema passed")
except Exception as e:
    record("meta_schema_valid", False, f"check_schema raised: {e}")

v = Draft202012Validator(schema)
def valid(obj):
    return len(list(v.iter_errors(obj))) == 0
def admitted_as_ok(obj):
    """Consumer gate: interpretation admitted only for schema-valid status==ok."""
    return valid(obj) and isinstance(obj, dict) and obj.get("status") == "ok"

# 2. captured ok envelope
record("captured_ok_validates", valid(capture), "retained after-close envelope (status ok, market_open false)")
record("captured_ok_admitted", admitted_as_ok(capture), "status == ok -> admitted (session-closed data, not a live read)")

# 3-6. synthetic source-derived fixtures (LABELED: not captures)
SYNTH = "SYNTHETIC source-derived shape from pinned source text — not a market capture"
fx_timeout = {"status": "error", "error": "OFFLINE_TIMEOUT",
              "updated_at": "2026-10-20T21:29:16.142252+00:00"}
fx_noquote = {"status": "error", "error": "no quote in feed (spot=0)",
              "updated_at": "2026-10-20T21:29:16.142252+00:00",
              "market_open": False, "spot": 0.0, "expiry": "2026-10-20"}
fx_quar = {"status": "quarantined",
           "quarantine_reason": "quote_as_of 2026-10-20T21:35:00+00:00 is in the future",
           "updated_at": "2026-10-20T21:29:16.142252+00:00",
           "market_open": False, "quote_as_of": "2026-10-20T21:35:00+00:00"}
fx_starting = {"status": "starting", "updated_at": None}
for name, fx in [("sparse_timeout_error", fx_timeout), ("no_quote_error", fx_noquote),
                 ("quarantined", fx_quar), ("starting", fx_starting)]:
    record(f"synthetic_{name}_validates", valid(fx), SYNTH)
    record(f"synthetic_{name}_withheld", not admitted_as_ok(fx),
           "non-ok status -> no interpretation admitted")

# 7. walls: numeric and null both admitted on an ok envelope
w = copy.deepcopy(capture)
w["gamma"]["call_wall"] = 768.0
w["gamma"]["put_wall"] = 765.0
record("walls_numeric_validate", valid(w) and admitted_as_ok(w), "call_wall/put_wall as numbers")
w2 = copy.deepcopy(capture)
w2["gamma"]["call_wall"] = None
w2["gamma"]["put_wall"] = None
w2["gamma"]["gamma_flip"] = None
w2["gamma"]["max_pain"] = None
record("walls_null_validate", valid(w2) and admitted_as_ok(w2), "walls/flip/max_pain as null (number-or-null)")

# 8. unknown status rejected outright
u = copy.deepcopy(capture)
u["status"] = "not-a-producer-status"
record("unknown_status_rejected", not valid(u), "no variant admits an unlisted status")

# 9. full body relabeled error: schema-valid as error variant, still withheld
r = copy.deepcopy(capture)
r["status"] = "error"
r["error"] = "OFFLINE_TIMEOUT"
record("relabeled_error_withheld", valid(r) and not admitted_as_ok(r),
       "gate is on status, not body shape")

# --- rev3 boundary checks: sources coverage (review 6e22de72, probes 14-16) ---
s1 = copy.deepcopy(capture)
s1["sources"]["nasdaq"]["as_of"] = None
s1["sources"]["nasdaq"]["n_strikes"] = 0
record("nasdaq_asof_null_validates", valid(s1) and admitted_as_ok(s1),
       "wings cache unavailable: nasdaq as_of null (unknown clock), n_strikes 0")
s2 = copy.deepcopy(capture)
s2["sources"]["rtd"]["as_of"] = None
record("chain_asof_null_validates", valid(s2) and admitted_as_ok(s2),
       "quote/chain timestamps absent: chain entry as_of null stays unknown")
s3 = copy.deepcopy(capture)
s3["sources"] = {"vendor_delayed": {"as_of": "2026-10-20T21:14:00+00:00", "delay": "~15min", "n_strikes": 146},
                 "nasdaq": dict(capture["sources"]["nasdaq"])}
s3["n_strikes_rtd_live"] = 0
record("alternate_provider_key_validates", valid(s3) and admitted_as_ok(s3),
       "dynamic chain-provider key admitted with its own declared delay; never relabeled realtime")

receipt = {
    "packet": "muse-main-producer-20261020-rev3",
    "producer_pin": "b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e",
    "inputs": {"feed_all.schema.json": sha(schema_raw),
               "envelope-ok-afterclose-20261020.json": sha(cap_raw)},
    "checks": checks,
    "summary": {"passed": sum(1 for c in checks if c["pass"]), "total": len(checks)},
}
with open(os.path.join(HERE, "schema-check-receipt.json"), "w") as f:
    json.dump(receipt, f, indent=1)
print(json.dumps(receipt["summary"]))
for c in checks:
    print(("PASS" if c["pass"] else "FAIL"), c["check"])
sys.exit(0 if receipt["summary"]["passed"] == receipt["summary"]["total"] else 1)
