#!/usr/bin/env python3
"""
Max-pain milestone checker.

Anik wants lead/lag analysis at 5, 30, and 365 trading days of logged data —
not every day.

Usage:
  python3 maxpain_milestones.py          -> prints "READY <n>" or "QUIET"
  python3 maxpain_milestones.py --mark N -> records milestone N as reported

A "trading day" = an expiry with >= 20 market-open records in the history log.
"""

import json
import os
import sys

LOG_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_history.jsonl")
STATE_PATH = os.path.expanduser(
    "~/workspace/goals/0dte-tape-alert-watch/hidden_files/maxpain_milestones.json")
MILESTONES = [5, 30, 365]
MIN_RECORDS_PER_DAY = 20


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"reported": []}


def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE_PATH)


def trading_days():
    per_expiry = {}
    try:
        with open(LOG_PATH) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("market_open") and r.get("expiry"):
                    per_expiry[r["expiry"]] = per_expiry.get(r["expiry"], 0) + 1
    except FileNotFoundError:
        return 0
    return sum(1 for n in per_expiry.values() if n >= MIN_RECORDS_PER_DAY)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--mark":
        n = int(sys.argv[2])
        s = load_state()
        if n not in s["reported"]:
            s["reported"].append(n)
            save_state(s)
        print(f"marked {n}")
        return

    days = trading_days()
    reported = set(load_state().get("reported", []))
    for m in MILESTONES:
        if days >= m and m not in reported:
            print(f"READY {m} | {days} trading days logged")
            return
    print(f"QUIET | {days} trading days logged")


if __name__ == "__main__":
    main()
