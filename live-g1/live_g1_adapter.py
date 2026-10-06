#!/usr/bin/env python3
"""
LIVE-G1 v1 (R1): Versioned read-only adapter over the 0DTE backend.

Source pin: 8649ad54 (J1-F P1, accepted)
Adapter version: live-g1/v1

R1 fixes (per reviewer harness):
1. preserve_existing_quote_observation_clock: use quote_as_of when present,
   never substitute snapshot ts for the quote source clock.
2. receipt_clock_missing_stays_unknown: SQLite has no receipt clock;
   received_at stays None, never fabricated from ts.
3. source_mix_not_promoted_to_rtd_live: respect src_mix; zero RTD sources
   must not be labeled RTD.
4. unknown_oi_vintage_not_inferred: oi_vintage stays None unless the record
   carries actual OI vintage info; never infer from record date.
5. accepted_expected_move_column_mapped: map exp_move_dollars column.
6. disconnected_old_data_not_fresh: disconnection + old data = stale,
   even during wall-clock market hours.
7. unknown_invalid_naive_future_clocks_not_fresh: None/bad/naive/future
   clocks are stale/unavailable, never fresh.
8. accepted_gex_history_map_becomes_real_cells: parse gex_m dict into cells.
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

INTERPRETER_URL = "http://localhost:8787"
# Allow tests to override "now"
_NOW_OVERRIDE = None


def _now():
    if _NOW_OVERRIDE is not None:
        return _NOW_OVERRIDE
    return datetime.now(timezone.utc)


def utc_now():
    return _now().isoformat()


def check_interpreter():
    """Check if the interpreter is reachable. Read-only, no side effects."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{INTERPRETER_URL}/feed/maxpain", timeout=5) as r:
            data = json.load(r)
            return True, data.get("received_at") or data.get("timestamp")
    except Exception as e:
        return False, str(e)


def _parse_clock(s):
    """
    Parse a clock string. Returns (dt, quality) where quality is one of:
    'ok', 'missing', 'invalid', 'naive', 'future'.
    Never raises.
    """
    if s is None:
        return None, "missing"
    if not isinstance(s, str):
        return None, "invalid"
    s = s.strip()
    if not s:
        return None, "missing"
    try:
        # Handle Z suffix
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None, "invalid"
    if dt.tzinfo is None:
        return dt, "naive"
    now = _now()
    # Future: more than 5 minutes ahead (allow small clock skew)
    if (dt - now).total_seconds() > 300:
        return dt, "future"
    return dt, "ok"


def _is_market_open(now=None):
    """Market hours: 13:30-20:00 UTC Mon-Fri."""
    now = now or _now()
    is_weekday = now.weekday() < 5
    mins = now.hour * 60 + now.minute
    return is_weekday and (810 <= mins < 1200)


def get_status():
    """GET /adapter/v1/status"""
    interp_ok, interp_info = check_interpreter()

    db_count = 0
    db_latest = None
    db_latest_dt = None
    if TAPE_DB.exists():
        try:
            conn = sqlite3.connect(f"file:{TAPE_DB}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), MAX(ts) FROM snapshots")
            row = cur.fetchone()
            db_count, db_latest = row[0], row[1]
            if db_latest:
                db_latest_dt, _ = _parse_clock(db_latest)
            conn.close()
        except Exception:
            pass

    journal_count = 0
    journal_latest = None
    if JOURNAL.exists():
        try:
            with open(JOURNAL) as f:
                lines = f.readlines()
                journal_count = len(lines)
                if lines:
                    rec = json.loads(lines[-1])
                    journal_latest = rec.get("ts")
        except Exception:
            pass

    now = _now()
    market_open = _is_market_open(now)

    # R2 stale determination: data age and clock quality dominate.
    # - No data → stale (never fresh)
    # - Future/invalid clock → stale (never fresh)
    # - Old data (>15min) → stale, even when interpreter reachable
    # - Disconnected → stale, even with recent data (last-good visibly stale)
    # - Reconnect without newer data → still stale (age-based, not connectivity)
    latest_dt = db_latest_dt
    _, clock_quality = _parse_clock(db_latest)
    data_age_s = None
    if latest_dt is not None and latest_dt.tzinfo is not None:
        data_age_s = (now - latest_dt).total_seconds()

    stale = False
    stale_reason = None

    # R2: no data is never fresh
    if db_latest is None:
        stale = True
        stale_reason = "no snapshot data available"
    # R2: future/invalid clock is never fresh
    elif clock_quality in ("future", "invalid", "naive"):
        stale = True
        stale_reason = f"latest data clock is {clock_quality}; cannot establish freshness"
    # R2: old data is stale regardless of connectivity
    elif data_age_s is not None and data_age_s > 900:
        stale = True
        if not interp_ok:
            stale_reason = "interpreter disconnected and data is old"
        else:
            stale_reason = "data older than 15 minutes"
    # R2: disconnected → last-good shown as stale, even if recent
    elif not interp_ok:
        stale = True
        stale_reason = "interpreter disconnected; showing last-good data as stale"
    # Outside market hours → stale
    elif not market_open:
        stale = True
        mins = now.hour * 60 + now.minute
        if now.weekday() >= 5:
            stale_reason = "weekend; last record from Friday close"
        elif mins >= 1200 or mins < 810:
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
    """
    Wrap a value with full provenance.

    R1 fixes:
    - received_at=None stays None (never fabricated).
    - source_at=None/invalid/naive/future → stale=True (never fresh).
    - oi_vintage=None stays None (never inferred).
    """
    unavailable = value is None

    # R1 fix #7: validate the clock; bad clocks are never fresh.
    _, quality = _parse_clock(source_at)
    if unavailable:
        stale = False  # unavailable dominates; stale is meaningless
    elif quality != "ok":
        stale = True
    else:
        # Valid clock: stale if older than 15 minutes
        dt, _ = _parse_clock(source_at)
        age = (_now() - dt).total_seconds()
        stale = age > 900

    field = {
        "value": value,
        "unit": unit,
        "source": source,
        "source_at": source_at,
        "received_at": received_at,  # None stays None (R1 fix #2)
        "stale": stale,
        "unavailable": unavailable,
    }
    # R1 fix #4: oi_vintage stays None unless actually provided
    if oi_vintage is not None:
        field["oi_vintage"] = oi_vintage
    else:
        field["oi_vintage"] = None
    return field


def _spot_source_label(record):
    """
    R1 fix #3, R2 fix: respect src_mix. Zero RTD sources must not be labeled RTD.
    Unknown/unparseable counts ("None rtd") must not claim RTD provenance.
    """
    src_mix = record.get("src_mix") or ""
    src_mix_lower = src_mix.lower()
    if "rtd" in src_mix_lower:
        import re
        m = re.search(r"(\d+)\s*rtd", src_mix_lower)
        if m:
            count = int(m.group(1))
            if count == 0:
                if "nasdaq" in src_mix_lower:
                    return "nasdaq wide-chain (delayed)"
                return "delayed (no RTD sources)"
            # Positive count: RTD is plausible
            return "gex.stepdad.finance RTD"
        # "rtd" mentioned but count unparseable (e.g., "None rtd"):
        # cannot authenticate RTD provenance
        return f"unverified source mix ({src_mix})"
    if src_mix:
        return f"mixed ({src_mix})"
    return "quote source (unspecified)"


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
    ts = r.get("ts")

    # R1 fix #1, R2: use quote_as_of for spot's source clock when present.
    # R2: missing quote_as_of stays None/unknown, NEVER fallback to ts.
    quote_as_of = r.get("quote_as_of")
    nasdaq_as_of = r.get("nasdaq_as_of")

    # R1 fix #2: SQLite has no receipt clock; received_at stays None
    received_at = None

    # R1 fix #4: oi_vintage only if record carries it
    oi_vintage = r.get("oi_vintage") or r.get("oi_as_of")

    # R1 fix #3: honest source label from src_mix
    spot_source = _spot_source_label(r)

    # R1 fix #5: map exp_move_dollars
    exp_move = r.get("exp_move_dollars")
    if exp_move is None:
        exp_move = r.get("expected_move")

    COMPUTED = "computed from OI"

    return {
        "adapter_version": ADAPTER_VERSION,
        "backend_pin": BACKEND_PIN,
        "recorded_at": ts,
        "fields": {
            "spot": wrap_field(
                r.get("spot"), "USD", spot_source,
                quote_as_of,  # R2: None stays None, never ts fallback
                received_at,  # R1 #2: None
            ),
            "max_pain": wrap_field(r.get("max_pain"), "USD", COMPUTED, ts, received_at, oi_vintage),
            "gamma_flip": wrap_field(r.get("gamma_flip"), "USD", COMPUTED, ts, received_at),
            "call_wall": wrap_field(r.get("call_wall"), "USD", COMPUTED, ts, received_at),
            "put_wall": wrap_field(r.get("put_wall"), "USD", COMPUTED, ts, received_at),
            "pin_score": wrap_field(r.get("pin_score"), "0-100", COMPUTED, ts, received_at),
            "expected_move": wrap_field(exp_move, "USD", "ATM straddle", ts, received_at),
            "gamma_regime": wrap_field(r.get("gamma_regime"), "label", COMPUTED, ts, received_at),
            "call_oi": wrap_field(r.get("call_oi"), "contracts", "nasdaq wide-chain (delayed)", nasdaq_as_of, received_at, oi_vintage),
            "put_oi": wrap_field(r.get("put_oi"), "contracts", "nasdaq wide-chain (delayed)", nasdaq_as_of, received_at, oi_vintage),
        },
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
            "SELECT ts, spot, max_pain, gamma_flip, call_wall, put_wall, pin_score, "
            "exp_move_dollars, quote_as_of, nasdaq_as_of, src_mix "
            "FROM snapshots ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        records = []
        for row in cur.fetchall():
            d = dict(row)
            # R1 fix #5: map exp_move_dollars
            if "exp_move_dollars" in d:
                d["expected_move"] = d.pop("exp_move_dollars")
            d["recorded_at"] = d.pop("ts")
            records.append(d)
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
    """
    GET /adapter/v1/heatmap.

    R1 fix #8: accepted gex_history.jsonl format is
    {"ts":..., "expiry":..., "spot":..., "gex_m":{"765.0":0.02,...},
     "gex_formula":"v2", "gex_units":"..."}
    Parse gex_m dict into individual cells. Zero values preserved.
    """
    if not GEX_HISTORY.exists():
        return {"adapter_version": ADAPTER_VERSION, "error": "gex_history.jsonl not found", "cells": []}
    try:
        cells = []
        with open(GEX_HISTORY) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = rec.get("ts") or rec.get("recorded_at")
                expiry = rec.get("expiry")
                formula = rec.get("gex_formula") or rec.get("formula")
                units = rec.get("gex_units")
                gex_m = rec.get("gex_m")
                if isinstance(gex_m, dict):
                    for strike_s, gex_v in gex_m.items():
                        try:
                            strike = float(strike_s)
                        except Exception:
                            continue
                        # Preserve zero as a real value (not missing)
                        # R2: preserve expiry identity per cell
                        cells.append({
                            "recorded_at": ts,
                            "expiry": expiry,
                            "strike": strike,
                            "gex": gex_v,
                            "formula": formula,
                            "units": units,
                        })
                else:
                    # Fallback: flat record format
                    if rec.get("strike") is not None:
                        cells.append({
                            "recorded_at": ts,
                            "expiry": expiry,
                            "strike": rec.get("strike"),
                            "gex": rec.get("gex"),
                            "formula": formula,
                            "units": units,
                        })
        return {
            "adapter_version": ADAPTER_VERSION,
            "backend_pin": BACKEND_PIN,
            "cell_count": len(cells),
            "note": "missing cells are gaps, not zeros; zero gex preserved as value",
            "cells": cells[-2000:],
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
