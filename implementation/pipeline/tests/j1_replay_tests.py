"""J1 broader restart/replay tests — offline, synthetic, no network.

Covers the cases J1 items 3 and 5 require beyond the reviewer's named
fixtures: separate-process-equivalent restarts after each write (DB missing,
journal missing, strike history missing, truncated tail), equivalent
timestamps, same ts/different expiry, A,C,B,A backfill sequences, malformed
lines, and replay of events outside any tail window.

Run: python3 tests/j1_replay_tests.py   (exit 0 = all pass)
"""
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import tape_db  # noqa: E402
import maxpain_log as logger  # noqa: E402

NOW = dt.datetime(2026, 10, 5, 19, 59, tzinfo=dt.timezone.utc)
TS = NOW.isoformat()
EXPIRY = "2026-10-05"

results = []


def record(name, ok, observed=""):
    results.append((name, bool(ok), observed))
    print(("PASS " if ok else "FAIL ") + name +
          ("" if ok else f"  :: {observed}"))


def feed(spot=100, gex=0.02, formula="v2", ts=TS):
    return {"status": "ok", "updated_at": ts, "quote_as_of": ts,
            "expiry": EXPIRY, "spot": spot,
            "gamma": {"gex_formula": formula, "max_pain": 100,
                      "by_strike": [{"strike": 100, "net_gex_m": gex}]}}


class Ctx:
    """Isolated logger+DB environment (stands in for separate processes)."""

    def __init__(self):
        self.td = tempfile.TemporaryDirectory()
        self.p = pathlib.Path(self.td.name)
        tape_db.HIDDEN = str(self.p)
        tape_db.DB_PATH = str(self.p / "tape.db")
        tape_db.LOG_PATH = str(self.p / "main.jsonl")
        tape_db.GEX_PATH = str(self.p / "gex.jsonl")
        logger.LOG_PATH = str(self.p / "history.jsonl")
        logger.GEX_SNAP_PATH = str(self.p / "gex.jsonl")
        logger.LOCK_PATH = str(self.p / "logger.lock")
        logger.EVENTS_PATH = str(self.p / "absent-events.json")
        self._feed = feed()

    def run(self, feed_dict=None):
        logger.fetch = lambda: feed_dict if feed_dict is not None else self._feed
        logger.main()

    def con(self):
        c = tape_db.connect()
        tape_db.init_db(c)
        return c

    def snaps(self):
        with self.con() as c:
            return c.execute("SELECT ts, expiry, spot FROM snapshots").fetchall()

    def strikes(self):
        with self.con() as c:
            return [tuple(r) for r in c.execute(
                "SELECT strike, net_gex_m, gex_formula FROM gex_strikes ORDER BY strike")]

    def conflicts(self):
        with self.con() as c:
            return c.execute("SELECT COUNT(*) FROM mirror_conflicts").fetchone()[0]

    def journal_lines(self):
        p = self.p / "history.jsonl"
        return p.read_text().splitlines() if p.exists() else []

    def gex_lines(self):
        p = self.p / "gex.jsonl"
        return p.read_text().splitlines() if p.exists() else []


# 1. restart with DB missing: journal is authoritative, DB repaired
c = Ctx()
c.run()
assert len(c.snaps()) == 1
os.remove(c.p / "tape.db")
c.run()
record("restart_db_missing",
       len(c.snaps()) == 1 and len(c.journal_lines()) == 1
       and c.strikes() == [(100.0, 0.02, "v2")],
       f"snaps={c.snaps()} strikes={c.strikes()}")

# 2. restart with journal missing: DB projection rebuilds the journal line
c = Ctx()
c.run()
os.remove(c.p / "history.jsonl")
c.run()
lines = c.journal_lines()
record("restart_journal_missing",
       len(lines) == 1 and json.loads(lines[0])["spot"] == 100
       and len(c.snaps()) == 1,
       f"lines={len(lines)}")

# 3. restart with strike history missing: repaired from accepted event
c = Ctx()
c.run()
os.remove(c.p / "gex.jsonl")
c.run(feed(formula="v1"))  # revised feed must NOT leak into the repair
gl = c.gex_lines()
record("restart_strike_missing",
       len(gl) == 1 and json.loads(gl[0])["gex_m"] == {"100": 0.02}
       and json.loads(gl[0])["gex_formula"] == "v2",
       f"gex_lines={gl}")

# 4. truncated tail: partial last line is skipped, never fatal
c = Ctx()
c.run()
with open(c.p / "history.jsonl", "a") as fh:
    fh.write('{"ts": "2026-10-05T19:59:00+00:00", "expiry": "2026-10-0')
c.run()
record("truncated_tail",
       len(c.snaps()) == 1 and len(c.journal_lines()) == 2,
       f"snaps={len(c.snaps())}")

# 5. equivalent timestamps: different offset spellings, one identity
c = Ctx()
with c.con() as con:
    r1 = tape_db.mirror_record({"ts": "2026-10-05T14:00:00+00:00",
                                "expiry": EXPIRY, "spot": 100}, {"100": 0.02}, con)
    r2 = tape_db.mirror_record({"ts": "2026-10-05T10:00:00-04:00",
                                "expiry": EXPIRY, "spot": 100}, {"100": 0.02}, con)
record("equivalent_timestamps",
       r1["status"] == "inserted" and r2["status"] == "duplicate"
       and len(c.snaps()) == 1,
       f"{r1['status']}/{r2['status']} snaps={len(c.snaps())}")

# 6. same ts, different expiry: distinct events
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": "2026-10-05", "spot": 100},
                          {"100": 0.02}, con)
    tape_db.mirror_record({"ts": TS, "expiry": "2026-10-06", "spot": 100},
                          {"100": 0.02}, con)
record("same_ts_different_expiry", len(c.snaps()) == 2,
       f"snaps={len(c.snaps())}")

# 7. backfill A,C,B,A: accept, conflict, accept-new, duplicate; dry == real
c = Ctx()
A = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2"}
C = {"ts": TS, "expiry": EXPIRY, "spot": 200, "gex_formula": "v2"}  # conflict
B = {"ts": "2026-10-05T20:00:00+00:00", "expiry": EXPIRY, "spot": 101,
     "gex_formula": "v2"}
gA = {"ts": TS, "expiry": EXPIRY, "gex_m": {"100": 0.02}, "gex_formula": "v2"}
gC = {"ts": TS, "expiry": EXPIRY, "gex_m": {"100": 9.99}, "gex_formula": "v2"}
with open(c.p / "main.jsonl", "w") as fh:
    for r in (A, C, B, A):
        fh.write(json.dumps(r) + "\n")
    fh.write("not json at all\n")
with open(c.p / "gex.jsonl", "w") as fh:
    for g in (gA, gC):
        fh.write(json.dumps(g) + "\n")
with c.con() as con:
    dry = tape_db.backfill(con, dry_run=True)
    real = tape_db.backfill(con)
record("backfill_ACBA_dry_equals_real", dry == real, f"dry={dry} real={real}")
record("backfill_ACBA_verdicts",
       real["snap_accepted"] == 2 and real["snap_conflict"] == 1
       and real["snap_duplicate"] == 1 and real["snap_rejected"] == 1
       and real["gex_accepted"] == 1 and real["gex_conflict"] == 1,
       str(real))
record("backfill_ACBA_no_hybrid",
       c.strikes() == [(100.0, 0.02, "v2")] and len(c.snaps()) == 2
       and c.conflicts() == 2,
       f"strikes={c.strikes()} snaps={len(c.snaps())}")

# 8. replay finds events anywhere in the file, not just a tail window
c2 = Ctx()
c2.run()
accepted = c2.journal_lines()[0]
filler = {"ts": "2000-01-01T00:00:00+00:00", "expiry": EXPIRY, "spot": 1}
with open(c2.p / "history.jsonl", "w") as fh:
    fh.write(accepted + "\n")
    fh.write((json.dumps(filler) + "\n") * 3000)
n_before = len(c2.snaps())
c2.run()  # same feed -> must converge to duplicate, not insert
record("replay_outside_tail",
       len(c2.snaps()) == n_before == 1,
       f"snaps={len(c2.snaps())}")

# 9. conflict then legitimate retry: accepted event untouched, then converges
c = Ctx()
c.run()
c.run(feed(spot=101, gex=0.5))   # conflict, quarantined
c.run()                            # original feed again -> duplicate
record("conflict_then_retry",
       len(c.snaps()) == 1 and c.snaps()[0][2] == 100
       and c.strikes() == [(100.0, 0.02, "v2")] and c.conflicts() == 1,
       f"snaps={c.snaps()} conflicts={c.conflicts()}")

# ---- J1-B boundary contracts (committed regression) ----
# 10. new event after an unterminated tail stays independently parseable
c = Ctx()
c.run()
with open(c.p / "history.jsonl", "a") as fh:
    fh.write('{"ts": "truncated')
c.run(feed(ts="2026-10-05T20:00:00+00:00"))
lines = [json.loads(ln) for ln in c.journal_lines()[2:]]
record("j1b_truncated_tail_framing",
       any(ln.get("ts") == "2026-10-05T20:00:00+00:00" for ln in lines)
       and len(c.snaps()) == 2,
       f"snaps={len(c.snaps())}")

# 11. backfill rebuilds DB strikes from the journal's embedded accepted map
c = Ctx()
rec = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
       "gex_m": {"100": 0.02}}
with open(c.p / "main.jsonl", "w") as fh:
    fh.write(json.dumps(rec) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1b_embedded_map_rebuild",
       c.strikes() == [(100.0, 0.02, "v2")]
       and counts["snap_accepted"] == 1,
       f"strikes={c.strikes()} counts={counts}")

# 12. disjoint strike from a rejected event is never added (no hybrid)
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
with open(c.p / "main.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 200,
                         "gex_formula": "v2"}) + "\n")
with open(c.p / "gex.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY,
                         "gex_m": {"101": 3}, "gex_formula": "v2"}) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1b_disjoint_strike_conflict",
       c.strikes() == [(100.0, 0.02, "v2")]
       and counts["gex_conflict"] == 1,
       f"strikes={c.strikes()} counts={counts}")

# 13. explicitly empty map deletes a nonempty accepted map: conflict, and the
#     logger and direct mirror agree on the verdict
c = Ctx()
c.run()
empty_feed = dict(feed(), gamma={"gex_formula": "v2", "by_strike": []})
c.run(empty_feed)
logger_conflicts = c.conflicts()
with c.con() as con:
    rec0 = json.loads(c.journal_lines()[0])
    direct = tape_db.mirror_record(rec0, {}, con)
record("j1b_explicit_empty_map_conflict",
       logger_conflicts == 1 and direct["status"] == "conflict"
       and len(c.snaps()) == 1,
       f"logger_conflicts={logger_conflicts} direct={direct['status']}")

# 14. logger repairs a missing DB strike projection from accepted content
c = Ctx()
c.run()
with c.con() as con:
    con.execute("DELETE FROM gex_strikes")
    con.commit()
c.run()
record("j1b_db_strike_repair", c.strikes() == [(100.0, 0.02, "v2")],
       f"strikes={c.strikes()}")

# 15. same strike value but changed formula is a semantic conflict
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
with open(c.p / "gex.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY,
                         "gex_m": {"100": 0.02},
                         "gex_formula": "v1"}) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1b_formula_only_conflict",
       counts["gex_conflict"] == 1 and c.conflicts() == 1
       and c.strikes() == [(100.0, 0.02, "v2")],
       f"counts={counts} strikes={c.strikes()}")

# 16. strike-only change yields distinct kept/incoming semantic hashes
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {"100": 0.5}, con)
record("j1b_semantic_hash_distinct",
       v["status"] == "conflict" and v["kept"] != v["incoming"],
       f"status={v['status']} distinct={v['kept'] != v['incoming']}")

# 17. orphan strike line (no accepted parent) is quarantined, never accepted
c = Ctx()
with open(c.p / "gex.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY,
                         "gex_m": {"100": 0.02},
                         "gex_formula": "v2"}) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1b_orphan_quarantined",
       c.strikes() == [] and counts["gex_orphan"] == 1
       and c.conflicts() == 1,
       f"strikes={c.strikes()} counts={counts}")

# 18. valid JSON scalar/list lines are rejected, replay continues
c = Ctx()
with open(c.p / "main.jsonl", "w") as fh:
    fh.write("[]\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1b_nonobject_rejected",
       counts["snap_rejected"] == 1 and len(c.snaps()) == 0,
       f"counts={counts}")

# 19. canonical UTC identity persists across backfill and mirror
c = Ctx()
with open(c.p / "main.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": "2026-10-05T10:00:00-04:00",
                         "expiry": EXPIRY, "spot": 100,
                         "gex_formula": "v2"}) + "\n")
with c.con() as con:
    tape_db.backfill(con)
    v = tape_db.mirror_record({"ts": "2026-10-05T14:00:00+00:00",
                               "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {}, con)
record("j1b_offset_identity",
       len(c.snaps()) == 1 and v["status"] == "duplicate"
       and c.snaps()[0][0] == "2026-10-05T14:00:00+00:00",
       f"snaps={c.snaps()} verdict={v['status']}")

# ---- J1-C continuity contracts (committed regression) ----
# 20. changed embedded map in primary journal is a conflict (not silent)
c = Ctx()
with open(c.p / "main.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 100,
                         "gex_formula": "v2", "gex_m": {"100": 0.02}}) + "\n")
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 100,
                         "gex_formula": "v2", "gex_m": {"100": 0.5}}) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1c_embedded_map_change_conflict",
       counts["snap_conflict"] == 1 and c.conflicts() == 1
       and c.strikes() == [(100.0, 0.02, "v2")],
       f"counts={counts} strikes={c.strikes()}")

# 21. repeat backfill repairs missing strike projection from journal
c = Ctx()
with open(c.p / "main.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 100,
                         "gex_formula": "v2",
                         "gex_m": {"100": 0.02, "101": 0.03}}) + "\n")
with c.con() as con:
    tape_db.backfill(con)
    con.execute("DELETE FROM gex_strikes WHERE strike = 101")
    con.commit()
    tape_db.backfill(con)
record("j1c_repeat_backfill_repairs",
       c.strikes() == [(100.0, 0.02, "v2"), (101.0, 0.03, "v2")],
       f"strikes={c.strikes()}")

# 22. explicitly empty map persists; secondary line cannot add strikes
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {}, con)
with open(c.p / "gex.jsonl", "w") as fh:
    fh.write(json.dumps({"ts": TS, "expiry": EXPIRY,
                         "gex_m": {"100": 0.02},
                         "gex_formula": "v2"}) + "\n")
with c.con() as con:
    counts = tape_db.backfill(con)
record("j1c_explicit_empty_persists",
       c.strikes() == [] and counts["gex_accepted"] == 0,
       f"strikes={c.strikes()} counts={counts}")

# 23. lost nonempty projection + explicitly empty incoming is not duplicate
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
    con.execute("DELETE FROM gex_strikes")
    con.commit()
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {}, con)
record("j1c_lost_map_not_duplicate",
       v["status"] != "duplicate",
       f"status={v['status']}")

# 24. incompatible units are a semantic conflict
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2",
                           "gex_units": "USD millions per 1% spot move"},
                          {"100": 0.02}, con)
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2",
                               "gex_units": "USD millions per $1 spot move"},
                              {"100": 0.02}, con)
record("j1c_units_conflict", v["status"] == "conflict",
       f"status={v['status']}")

# 25. divergent DB projection is repaired from authoritative journal
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE snapshots SET spot = 200")
    con.commit()
c.run()
with c.con() as con:
    spot = con.execute("SELECT spot FROM snapshots").fetchone()[0]
record("j1c_divergence_repaired", spot == 100, f"db_spot={spot}")

# 26. J1-D: later superset payload in journal conflicts, does not repair.
# (Matches reviewer fixture: two lines, same core, second has superset map.)
c = Ctx()
with c.con() as con:
    a = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
         "gex_m": {"100": 0.02}}
    b = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
         "gex_m": {"100": 0.02, "101": 0.03}}
    with open(c.p / "main.jsonl", "w") as f:
        f.write(json.dumps(a) + "\n")
        f.write(json.dumps(b) + "\n")
    counts = tape_db.backfill(con)
    n_strikes = len(c.strikes())
record("j1d_superset_replay_conflict",
       n_strikes == 1 and counts["snap_conflict"] == 1,
       f"strikes={n_strikes} conflicts={counts['snap_conflict']}")

# 27. J1-D: explicitly empty primary map cannot grow via replay.
# (Matches reviewer fixture: line a empty, line b nonempty -> conflict.)
c = Ctx()
with c.con() as con:
    a = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
         "gex_m": {}}
    b = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
         "gex_m": {"100": 0.02}}
    with open(c.p / "main.jsonl", "w") as f:
        f.write(json.dumps(a) + "\n")
        f.write(json.dumps(b) + "\n")
    counts = tape_db.backfill(con)
    n_strikes = len(c.strikes())
record("j1d_empty_cannot_grow",
       n_strikes == 0 and counts["snap_conflict"] == 1,
       f"strikes={n_strikes} conflicts={counts['snap_conflict']}")

# 28. J1-D: divergent strike values are repaired, not left
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
c.run()  # logger should repair the divergent value
with c.con() as con:
    val = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
record("j1d_divergent_strike_repaired", abs(val - 0.02) < 1e-9, f"val={val}")

# 29. J1-D: logger carries units lineage; changed units conflict
c = Ctx()
f1 = feed()
f1["gamma"]["gex_units"] = "USD millions per 1% spot move"
c.run(f1)
f2 = feed()
f2["gamma"]["gex_units"] = "USD millions per $1 spot move"
c.run(f2)
rec = json.loads(c.journal_lines()[0])
record("j1d_units_lineage",
       c.conflicts() >= 1 and
       rec.get("gex_units") == "USD millions per 1% spot move",
       f"conflicts={c.conflicts()} units={rec.get('gex_units')}")

# 30. J1-D: ambiguous legacy aliases are quarantined
c = Ctx()
with c.con() as con:
    # Two rows, same normalized instant, different content.
    for ts, spot in [(TS, 100), ("2026-10-05T15:59:00-04:00", 200)]:
        con.execute(
            "INSERT INTO snapshots (ts, expiry, spot, gex_formula, payload_hash, gex_map_status) "
            "VALUES (?, ?, ?, 'v2', 'x', 'explicit')", (ts, EXPIRY, spot))
        con.execute(
            "INSERT INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula) "
            "VALUES (?, ?, 100, 0.02, 'v2')", (ts, EXPIRY))
    con.commit()
with c.con() as con:
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {"100": 0.02}, con)
    n = c.conflicts()
record("j1d_ambiguous_alias_quarantined",
       v["status"] == "conflict" and n >= 1,
       f"status={v['status']} conflicts={n}")

# 31. J1-D: direct superset mirror still conflicts (control)
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {"100": 0.02, "101": 0.03}, con)
    n_strikes = len(c.strikes())
record("j1d_direct_superset_conflict",
       v["status"] == "conflict" and n_strikes == 1,
       f"status={v['status']} strikes={n_strikes}")

# 32. J1-D: genuine missing projection still repairs (control)
c = Ctx()
c.run()
with c.con() as con:
    # Add a second strike via the journal, then delete it from DB.
    rec = json.loads(c.journal_lines()[0])
    rec["gex_m"] = {"100.0": 0.02, "101.0": 0.03}
    # First accept it properly via mirror.
    tape_db.mirror_record(
        {"ts": "2026-10-05T20:00:00+00:00", "expiry": EXPIRY, "spot": 100,
         "gex_formula": "v2"}, {"100": 0.02, "101": 0.03}, con)
    con.execute("DELETE FROM gex_strikes WHERE strike = 101")
    con.commit()
with c.con() as con:
    # Write the journal line and backfill.
    rec2 = {"ts": "2026-10-05T20:00:00+00:00", "expiry": EXPIRY, "spot": 100,
            "gex_formula": "v2", "gex_m": {"100.0": 0.02, "101.0": 0.03}}
    with open(c.p / "history.jsonl", "a") as f:
        f.write(json.dumps(rec2) + "\n")
    tape_db.backfill(con)
    n_strikes = len([s for s in c.strikes() if s[0] in (100.0, 101.0)])
record("j1d_genuine_repair", n_strikes == 2, f"strikes={n_strikes}")

# 33. J1-D: digest proves original content across restart.
# Write the accepted journal line, backfill, then backfill again (simulating
# restart) — the second run should see duplicates via digest match.
c = Ctx()
with c.con() as con:
    a = {"ts": TS, "expiry": EXPIRY, "spot": 100, "gex_formula": "v2",
         "gex_m": {"100": 0.02}}
    with open(c.p / "main.jsonl", "w") as f:
        f.write(json.dumps(a) + "\n")
    counts1 = tape_db.backfill(con)
with c.con() as con:
    counts2 = tape_db.backfill(con)
record("j1d_digest_survives_restart",
       counts1["snap_accepted"] == 1 and counts2["snap_duplicate"] == 1,
       f"accepted={counts1['snap_accepted']} duplicates={counts2['snap_duplicate']}")

# 34. J1-E: full core alias ambiguity (same spot/formula, different max_pain)
c = Ctx()
with c.con() as con:
    for ts, mp in [(TS, 100), ("2026-10-05T15:59:00-04:00", 101)]:
        con.execute(
            "INSERT INTO snapshots (ts, expiry, spot, max_pain, gex_formula, payload_hash, gex_map_status) "
            "VALUES (?, ?, 100, ?, 'v2', 'x', 'explicit')", (ts, EXPIRY, mp))
        con.execute(
            "INSERT INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula) "
            "VALUES (?, ?, 100, 0.02, 'v2')", (ts, EXPIRY))
    con.commit()
with c.con() as con:
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2", "max_pain": 100},
                              {"100": 0.02}, con)
record("j1e_full_core_alias_ambiguity", v["status"] == "conflict",
       f"status={v['status']}")

# 35. J1-E: full map alias ambiguity (same core, different map values)
c = Ctx()
with c.con() as con:
    for ts, gv in [(TS, 0.02), ("2026-10-05T15:59:00-04:00", 0.05)]:
        con.execute(
            "INSERT INTO snapshots (ts, expiry, spot, gex_formula, payload_hash, gex_map_status) "
            "VALUES (?, ?, 100, 'v2', 'x', 'explicit')", (ts, EXPIRY))
        con.execute(
            "INSERT INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula) "
            "VALUES (?, ?, 100, ?, 'v2')", (ts, EXPIRY, gv))
    con.commit()
with c.con() as con:
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {"100": 0.02}, con)
record("j1e_full_map_alias_ambiguity", v["status"] == "conflict",
       f"status={v['status']}")

# 36. J1-E: stored digest mismatch is conflict, not duplicate
c = Ctx()
with c.con() as con:
    tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                           "gex_formula": "v2"}, {"100": 0.02}, con)
    con.execute("UPDATE snapshots SET payload_hash = 'wrong-digest'")
    con.commit()
with c.con() as con:
    v = tape_db.mirror_record({"ts": TS, "expiry": EXPIRY, "spot": 100,
                               "gex_formula": "v2"}, {"100": 0.02}, con)
record("j1e_digest_mismatch_conflict", v["status"] == "conflict",
       f"status={v['status']}")

# 37. J1-E: unavailable accepted map cannot adopt new map
c = Ctx()
with c.con() as con:
    tape_db.insert_snapshot({"ts": TS, "expiry": EXPIRY, "spot": 100,
                             "gex_formula": "v2"}, con)
    with open(c.p / "main.jsonl", "w") as f:
        f.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 100,
                            "gex_formula": "v2", "gex_m": {"100": 0.02}}) + "\n")
    counts = tape_db.backfill(con)
record("j1e_unavailable_map_conflict", counts["snap_conflict"] >= 1,
       f"conflicts={counts['snap_conflict']}")

# 38. J1-E: backfill repairs divergent values
c = Ctx()
with c.con() as con:
    with open(c.p / "main.jsonl", "w") as f:
        f.write(json.dumps({"ts": TS, "expiry": EXPIRY, "spot": 100,
                            "gex_formula": "v2", "gex_m": {"100": 0.02}}) + "\n")
    tape_db.backfill(con)
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
    tape_db.backfill(con)
    val = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
record("j1e_backfill_repairs_values", abs(val - 0.02) < 1e-9, f"val={val}")

# 39. J1-E: logger repairs divergent formula
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET gex_formula = 'v1'")
    con.commit()
c.run()
with c.con() as con:
    formula = con.execute("SELECT gex_formula FROM gex_strikes").fetchone()[0]
record("j1e_logger_repairs_formula", formula == "v2", f"formula={formula}")

# 40. J1-E: secondary projection preserves source units
c = Ctx()
f = feed()
f["gamma"]["gex_units"] = "USD millions per $1 spot move"
c.run(f)
primary = json.loads(c.journal_lines()[0])
secondary = json.loads(c.gex_lines()[0])
record("j1e_secondary_units",
       primary.get("gex_units") == secondary.get("gex_units") ==
       "USD millions per $1 spot move",
       f"primary={primary.get('gex_units')} secondary={secondary.get('gex_units')}")

# 41. J1-E: DB-only digest mismatch quarantined
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
# Delete journals, run with tampered feed
import os
for fn in ["history.jsonl", "gex.jsonl"]:
    p = c.p / fn
    if p.exists():
        p.unlink()
f2 = feed()
f2["gamma"]["by_strike"][0]["net_gex_m"] = 0.5
c.run(f2)
record("j1e_db_digest_mismatch_quarantined", c.conflicts() >= 1,
       f"conflicts={c.conflicts()}")

# 42. J1-E: ambiguous logger does not append
c = Ctx()
with c.con() as con:
    for ts, spot in [(TS, 100), ("2026-10-05T15:59:00-04:00", 200)]:
        con.execute(
            "INSERT INTO snapshots (ts, expiry, spot, gex_formula, payload_hash, gex_map_status) "
            "VALUES (?, ?, ?, 'v2', 'x', 'explicit')", (ts, EXPIRY, spot))
    con.commit()
c.run()
journal_lines = c.journal_lines()
record("j1e_ambiguous_no_append", len(journal_lines) == 0 and c.conflicts() >= 1,
       f"journal_lines={len(journal_lines)} conflicts={c.conflicts()}")

# 43. J1-E: alias value repair uses resolved ts
c = Ctx()
c.run()
with c.con() as con:
    alias = "2026-10-05T15:59:00-04:00"
    for table in ["snapshots", "gex_strikes"]:
        con.execute(f"UPDATE {table} SET ts = ?", (alias,))
    con.commit()
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
c.run()
with c.con() as con:
    val = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
record("j1e_alias_repair_resolved_ts", abs(val - 0.02) < 1e-9, f"val={val}")

# 44. J1-F: backfill repair survives close/reopen (committed)
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
import tape_db as _tdb
import shutil
# Backfill reads from tape_db.LOG_PATH (main.jsonl); logger writes to history.jsonl
shutil.copy(str(c.p / "history.jsonl"), str(c.p / "main.jsonl"))
with c.con() as con:
    _tdb.backfill(con)
with c.con() as con:
    val = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
record("j1f_backfill_commit_durable", abs(val - 0.02) < 1e-9, f"val={val}")

# 45. J1-F: dry run overlay matches real (no DB mutation in dry)
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET net_gex_m = 0.5")
    con.commit()
shutil.copy(str(c.p / "history.jsonl"), str(c.p / "main.jsonl"))
# Also copy gex.jsonl for secondary
if (c.p / "gex.jsonl").exists():
    shutil.copy(str(c.p / "gex.jsonl"), str(c.p / "main_gex.jsonl"))
    _tdb.GEX_PATH = str(c.p / "main_gex.jsonl")
with c.con() as con:
    dry_counts = _tdb.backfill(con, dry_run=True)
with c.con() as con:
    val_dry = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
    real_counts = _tdb.backfill(con)
with c.con() as con:
    val_real = con.execute("SELECT net_gex_m FROM gex_strikes").fetchone()[0]
record("j1f_dry_no_write", abs(val_dry - 0.5) < 1e-9 and abs(val_real - 0.02) < 1e-9,
       f"dry_val={val_dry} real_val={val_real} dry={dry_counts} real={real_counts}")

# 46. J1-F: formula repair persists
c = Ctx()
c.run()
with c.con() as con:
    con.execute("UPDATE gex_strikes SET gex_formula = 'v1'")
    con.commit()
shutil.copy(str(c.p / "history.jsonl"), str(c.p / "main.jsonl"))
with c.con() as con:
    _tdb.backfill(con)
with c.con() as con:
    formula = con.execute("SELECT gex_formula FROM gex_strikes").fetchone()[0]
record("j1f_formula_repair_persists", formula == "v2", f"formula={formula}")

# 47. J1-F: extra strike removed
c = Ctx()
c.run()
with c.con() as con:
    con.execute("INSERT INTO gex_strikes (ts, expiry, strike, net_gex_m, gex_formula) VALUES (?, ?, 101, 0.5, 'v2')", (TS, EXPIRY))
    con.commit()
c.run()
with c.con() as con:
    n = con.execute("SELECT COUNT(*) FROM gex_strikes").fetchone()[0]
record("j1f_extra_strike_removed", n == 1, f"count={n}")

# 48. J1-F: alias insert preserves alias ts (no orphan)
c = Ctx()
c.run(feed_dict=dict(status='ok', updated_at=TS, quote_as_of=TS, expiry=EXPIRY, spot=100,
                     gamma=dict(gex_formula='v2', by_strike=[dict(strike=100, net_gex_m=0.02), dict(strike=101, net_gex_m=0.03)])))
with c.con() as con:
    alias = "2026-10-05T15:59:00-04:00"
    for table in ["snapshots", "gex_strikes"]:
        con.execute(f"UPDATE {table} SET ts = ?", (alias,))
    con.commit()
    con.execute("DELETE FROM gex_strikes WHERE strike = 101")
    con.commit()
c.run(feed_dict=dict(status='ok', updated_at=TS, quote_as_of=TS, expiry=EXPIRY, spot=100,
                     gamma=dict(gex_formula='v2', by_strike=[dict(strike=100, net_gex_m=0.02), dict(strike=101, net_gex_m=0.03)])))
with c.con() as con:
    rows = con.execute("SELECT ts, strike FROM gex_strikes ORDER BY strike").fetchall()
    ts_set = set(r[0] for r in rows)
record("j1f_alias_insert_no_orphan", len(ts_set) == 1 and alias in ts_set,
       f"rows={[(r[0], r[1]) for r in rows]}")

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} pass")
sys.exit(1 if failed else 0)
