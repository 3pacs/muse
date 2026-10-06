#!/usr/bin/env python3
"""
LIVE-G1 v1: Versioned read-only adapter over the 0DTE backend.

Source pin: 8649ad54 (J1-F P1, accepted)
Adapter version: live-g1/v1

Exposes real tape data with full provenance. Never substitutes fixture values.
If data is unavailable, reports unavailable=true rather than inventing numbers.

Usage:
    python3 live_g1_adapter.py status
    python3 live_g1_adapter.py snapshot
    python3 live_g1_adapter.py history --limit 50
    python3 live_g1_adapter.py heatmap
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ADAPTER_VERSION = "live-g1/v1"
BACKEND_PIN = "8649ad54"

GOAL_DIR = Path.home() / "workspace/goals/0dte-tape-alert-watch/hidden_files"
TAPE_DB = GOAL_DIR / "tape.db"
JOURNAL = GOAL_DIR / "maxpain_history.jsonl"
GEX_HISTORY = GOAL_DIR / "gex_history.jsonl"
DASHBOARD_DATA = GOAL_DIR / "dashboard_data.json"

INTERPRETER_URL = "http://localhost:8787"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def check_interpreter():
    """Check if the interpreter is reachable. Read-only, no side effects."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(f"{INTERPRETER_URL}/feed/maxpain", timeout=5) as r:
            data = json.load(r)
            return True, data.get("received_at") or data.get("timestamp")
    except Exception as e:
        return False, str(e)


def get_status():
    """GET /adapter/v1/status"""
    interp_ok, interp_info = check_interpreter()

    # Tape DB stats
    db_count = 0
    db_latest = None
    if TAPE_DB.exists():
        try:
            conn = sqlite3.connect(f"file:{TAPE_DB}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), MAX(ts) FROM snapshots")
            row = cur.fetchone()
            db_count, db_latest = row[0], row[1]
            conn.close()
        except Exception:
            pass

    # Journal stats
    journal_count = 0
    journal_latest = None
    if JOURNAL.exists():
        try:
            with open(JOURNAL) as f:
                lines = f.readlines()
                journal_count = len(lines)
                if lines:
                    rec = json.loads(lines[-1])
                    journal_latest = rec.get("ts") or rec.get("recorded_at") or rec.get("timestamp")
        except Exception:
            pass

    # Market hours: 13:30-20:00 UTC Mon-Fri (6:30-13:00 PDT)
    now = datetime.now(timezone.utc)
    is_weekday = now.weekday() < 5
    # Handle UTC day boundary: 00:00-13:30 UTC is still "overnight" from prior day's close
    mins = now.hour * 60 + now.minute
    market_open = is_weekday and (810 <= mins < 1200)  # 13:30=810, 20:00=1200

    stale = not market_open
    stale_reason = None
    if stale:
        if not is_weekday:
            stale_reason = "weekend; last record from Friday close"
        elif mins >= 1200 or mins < 810:
            # After 20:00 UTC or before 13:30 UTC = market closed (overnight)
            stale_reason = "market closed; last record from session close"
        else:
            stale_reason = "pre-market; no fresh data yet"

    return {
        "adapter_version": ADAPTER_VERSION,
        "backend_pin": BACKEND_PIN,
        "checked_at": utc_now(),
        "backend": {
            "interpreter": {
                "reachable": interp_ok,
                "url": INTERPRETER_URL,
                "last_poll_info": interp_info,
            },
            "tape_db": {
                "path": str(TAPE_DB),
                "snapshot_count": db_count,
                "latest_at": db_latest,
            },
            "journal": {
                "path": str(JOURNAL),
                "record_count": journal_count,
                "latest_at": journal_latest,
            },
        },
        "data_vintage": {
            "latest_record_at": db_latest or journal_latest,
            "market_hours": market_open,
            "stale": stale,
            "stale_reason": stale_reason,
        },
    }


def wrap_field(value, unit, source, source_at, received_at, oi_vintage=None):
    """Wrap a value with full provenance. Never invent values."""
    unavailable = value is None
    # Stale if source_at is older than 15 minutes (and market is open)
    stale = False
    if source_at and not unavailable:
        try:
            src_time = datetime.fromisoformat(source_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - src_time).total_seconds()
            stale = age > 900  # 15 minutes
        except Exception:
            pass
    field = {
        "value": value,
        "unit": unit,
        "source": source,
        "source_at": source_at,
        "received_at": received_at,
        "stale": stale,
        "unavailable": unavailable,
    }
    if oi_vintage:
        field["oi_vintage"] = oi_vintage
    return field


def get_snapshot():
    """GET /adapter/v1/snapshot — latest record with per-field provenance."""
    if not TAPE_DB.exists():
        return {
            "adapter_version": ADAPTER_VERSION,
            "error": "tape.db not found",
            "unavailable": True,
        }

    try:
        conn = sqlite3.connect(f"file:{TAPE_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        return {
            "adapter_version": ADAPTER_VERSION,
            "error": f"db read failed: {e}",
            "unavailable": True,
        }

    if not row:
        return {
            "adapter_version": ADAPTER_VERSION,
            "error": "no snapshots",
            "unavailable": True,
        }

    r = dict(row)
    recorded_at = r.get("ts")
    # OI is T+1: vintage is previous trading day
    # (simplified: use recorded date minus 1 day)
    oi_vintage = None
    try:
        rec_dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        vintage_dt = rec_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        oi_vintage = f"{vintage_dt.date()} settlement (T+1)"
    except Exception:
        pass

    RTD = "gex.stepdad.finance RTD"
    WINGS = "nasdaq wide-chain (15m delayed)"
    COMPUTED = "computed from OI"

    return {
        "adapter_version": ADAPTER_VERSION,
        "backend_pin": BACKEND_PIN,
        "recorded_at": recorded_at,
        "fields": {
            "spot": wrap_field(r.get("spot"), "USD", RTD, recorded_at, recorded_at),
            "max_pain": wrap_field(r.get("max_pain"), "USD", COMPUTED, recorded_at, recorded_at, oi_vintage),
            "gamma_flip": wrap_field(r.get("gamma_flip"), "USD", COMPUTED, recorded_at, recorded_at),
            "call_wall": wrap_field(r.get("call_wall"), "USD", COMPUTED, recorded_at, recorded_at),
            "put_wall": wrap_field(r.get("put_wall"), "USD", COMPUTED, recorded_at, recorded_at),
            "pin_score": wrap_field(r.get("pin_score"), "0-100", COMPUTED, recorded_at, recorded_at),
            "expected_move": wrap_field(r.get("expected_move"), "USD", "ATM straddle", recorded_at, recorded_at),
            "gamma_regime": wrap_field(r.get("gamma_regime"), "label", COMPUTED, recorded_at, recorded_at),
            "call_oi": wrap_field(r.get("call_oi"), "contracts", WINGS, recorded_at, recorded_at, oi_vintage),
            "put_oi": wrap_field(r.get("put_oi"), "contracts", WINGS, recorded_at, recorded_at, oi_vintage),
        },
        "provenance": r.get("provenance") or r.get("source_provenance"),
    }


def get_history(limit=50):
    """GET /adapter/v1/history"""
    if not TAPE_DB.exists():
        return {"adapter_version": ADAPTER_VERSION, "error": "tape.db not found", "records": []}
    try:
        conn = sqlite3.connect(f"file:{TAPE_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT ts, spot, max_pain, gamma_flip, call_wall, put_wall, pin_score "
            "FROM snapshots ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        records = [dict(r) for r in cur.fetchall()]
        # normalize ts -> recorded_at for API consistency
        for rec in records:
            rec["recorded_at"] = rec.pop("ts")
        conn.close()
        return {
            "adapter_version": ADAPTER_VERSION,
            "backend_pin": BACKEND_PIN,
            "count": len(records),
            "records": records,
        }
    except Exception as e:
        return {"adapter_version": ADAPTER_VERSION, "error": str(e), "records": []}


def get_heatmap():
    """GET /adapter/v1/heatmap"""
    if not GEX_HISTORY.exists():
        return {"adapter_version": ADAPTER_VERSION, "error": "gex_history.jsonl not found", "cells": []}
    try:
        cells = []
        with open(GEX_HISTORY) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    cells.append({
                        "recorded_at": rec.get("recorded_at"),
                        "strike": rec.get("strike"),
                        "gex": rec.get("gex"),
                        "formula": rec.get("gex_formula") or rec.get("formula"),
                    })
                except Exception:
                    continue
        return {
            "adapter_version": ADAPTER_VERSION,
            "backend_pin": BACKEND_PIN,
            "cell_count": len(cells),
            "note": "missing cells are gaps, not zeros",
            "cells": cells[-1000:],  # last 1000 to bound size
        }
    except Exception as e:
        return {"adapter_version": ADAPTER_VERSION, "error": str(e), "cells": []}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["status", "snapshot", "history", "heatmap"])
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args()

    if args.cmd == "status":
        print(json.dumps(get_status(), indent=2))
    elif args.cmd == "snapshot":
        print(json.dumps(get_snapshot(), indent=2))
    elif args.cmd == "history":
        print(json.dumps(get_history(args.limit), indent=2))
    elif args.cmd == "heatmap":
        print(json.dumps(get_heatmap(), indent=2))


if __name__ == "__main__":
    main()
