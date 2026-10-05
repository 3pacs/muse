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

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} pass")
sys.exit(1 if failed else 0)
