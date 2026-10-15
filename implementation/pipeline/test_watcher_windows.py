#!/usr/bin/env python3
"""Synthetic tests for the watcher spot_move window fix (2026-10-12).

Reproduces the Oct 5/8 failure (slow all-day drift reported as a
'~375m' spot_move) and checks real 15m/30m moves still fire.
Run: python3 test_watcher_windows.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watcher import displacement, spot_move_trigger

T0 = 1_700_000_000.0
fails = []

def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} {name}: got={got} want={want}")
    if not ok:
        fails.append(name)

def series(step_s, n, price_fn):
    return [{"t": T0 + i * step_s, "spot": price_fn(i), "mp": 0} for i in range(n)]

def evaluate(hist, spot):
    now = hist[-1]["t"]
    p15, m15 = displacement(hist, now, spot, 900)
    p30, m30 = displacement(hist, now, spot, 1800)
    trig, pct, mins = spot_move_trigger(p15, m15, p30, m30)
    return trig, pct, mins, m15, m30

# 1. Slow all-day drift: +0.62% over ~375m, readings every 2m.
#    Old code fired (ref = open). New: 15m/30m slices are tiny -> no fire.
hist = series(120, 189, lambda i: 770.0 * (1 + 0.0062 * i / 188))
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("slow-drift no-fire", trig, False)
check("slow-drift mins15 ~16", 14 <= m15 <= 18, True)
check("slow-drift mins30 ~30", 28 <= m30 <= 32, True)

# 2. Real 15m move: flat, then +0.50% in the last ~14m.
def p2(i):
    base = 770.0
    if i < 20:
        return base
    return base * (1 + 0.0050 * (i - 20) / 7)  # 7 steps of 2m = 14m ramp
hist = series(120, 28, p2)
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("fast-15m fires", trig, True)
check("fast-15m pct ~0.50", abs(pct - 0.50) < 0.08, True)
check("fast-15m mins labelled 10-25", 10 <= mins <= 25, True)

# 3. Real 30m move: +0.75% spread over ~28m, only +0.38% in last 15m.
def p3(i):
    base = 770.0
    if i < 10:
        return base
    return base * (1 + 0.0075 * (i - 10) / 14)  # 14 steps of 2m = 28m
hist = series(120, 25, p3)
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("fast-30m fires", trig, True)
check("fast-30m mins labelled 20-45", 20 <= mins <= 45, True)

# 4. Gap trap: two readings 375m apart, +0.62% between them.
#    The only candidate refs are ~375m old -> window tolerance rejects.
hist = [{"t": T0, "spot": 770.0, "mp": 0},
        {"t": T0 + 375 * 60, "spot": 770.0 * 1.0062, "mp": 0}]
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("gap no-fire", trig, False)

# 5. Young session: only 8m of history -> no ref old enough -> no fire
#    even on a sharp +0.60% pop (nothing to measure a window against).
hist = series(120, 5, lambda i: 770.0 * (1 + 0.0015 * i))
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("young-session no-fire", trig, False)

# 6. Down move symmetry: -0.45% in ~16m fires, direction from pct sign.
def p6(i):
    base = 770.0
    if i < 15:
        return base
    return base * (1 - 0.0045 * (i - 15) / 8)
hist = series(120, 24, p6)
trig, pct, mins, m15, m30 = evaluate(hist, hist[-1]["spot"])
check("down-15m fires", trig, True)
check("down-15m pct negative", pct < 0, True)

print("\n%d failure(s)" % len(fails))
sys.exit(1 if fails else 0)
