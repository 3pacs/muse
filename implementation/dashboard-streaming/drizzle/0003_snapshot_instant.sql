-- ADOPT-C1-R1: chronological snapshot identity.
-- Adds the validated-UTC-instant key (epoch milliseconds) for the
-- snapshots table and backfills it from the stored `updated_at` text.
-- Additive and provenance-preserving: no row is deleted, merged or
-- rewritten; `updated_at` and `payload_json` keep their original bytes,
-- including legacy rows that spell one instant with different timezone
-- offsets.
--
-- COMPLETION (review round 2): the backfill must produce exactly the
-- application admission key (the F1 aware-instant parser:
-- AWARE_TS_RE + Date.parse) for every admitted spelling, and leave
-- inadmissible clocks UNKEYED (instant_ms NULL). SQLite's unixepoch
-- alone diverges from that parser — it rejects compact offsets
-- (+0200), rounds sub-millisecond fractions instead of truncating,
-- parses timezone-less strings the application rejects, and rolls
-- out-of-range components over — so the expression below computes
-- the instant arithmetically instead: the naive date/time prefix is
-- converted as UTC, the zone offset parsed from the suffix is
-- subtracted, and the fractional-second digits are truncated to
-- milliseconds by string slicing, matching Date.parse semantics.
--
-- PARITY ROUND (review round 3): the guards now enforce the WHOLE
-- spelling, not just its positions: the date/time prefix must match
-- the admitted digit shape end-to-end, the string must be exactly
-- datetime + zone or datetime + '.' + all-digit fraction + zone
-- (junk suffixes like `.5junkZ`, `00junkZ`, `.1xZ` stay unkeyed),
-- and the one rollover the application parser admits — exactly
-- midnight spelled 24:00 / 24:00:00 with an absent or all-zero
-- fraction — is keyed to the next day's 00:00:00, while 24:00:01,
-- 24:01 and 24:30 stay rejected. Verified equivalent to the
-- application parser on a 53-spelling battery (offline harness
-- R09), including every reviewer witness.
ALTER TABLE snapshots ADD COLUMN instant_ms INTEGER;
--> statement-breakpoint
UPDATE snapshots SET instant_ms =
  unixepoch(substr(updated_at, 1, 10) || ' ' || CASE WHEN substr(updated_at, 17, 1) = ':' THEN substr(updated_at, 12, 8) ELSE substr(updated_at, 12, 5) || ':00' END) * 1000
  - (CASE WHEN substr(updated_at, -1) = 'Z' THEN 0
      WHEN substr(updated_at, -3, 1) = ':' THEN (CASE WHEN substr(updated_at, -6, 1) = '+' THEN 1 ELSE -1 END) * (CAST(substr(updated_at, -5, 2) AS INTEGER) * 3600 + CAST(substr(updated_at, -2, 2) AS INTEGER) * 60)
      ELSE (CASE WHEN substr(updated_at, -5, 1) = '+' THEN 1 ELSE -1 END) * (CAST(substr(updated_at, -4, 2) AS INTEGER) * 3600 + CAST(substr(updated_at, -2, 2) AS INTEGER) * 60) END) * 1000
  + (CASE WHEN instr(updated_at, '.') = 20 THEN CAST(substr(substr(updated_at, 21, length(updated_at) - 20 - (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END)) || '000', 1, 3) AS INTEGER) ELSE 0 END)
WHERE instant_ms IS NULL
  AND ((substr(updated_at, 17, 1) = ':' AND substr(updated_at, 1, 19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
    OR (substr(updated_at, 17, 1) != ':' AND substr(updated_at, 1, 16) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]'))
  AND (CASE (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END)
    WHEN 1 THEN substr(updated_at, -1) = 'Z'
    WHEN 6 THEN substr(updated_at, -6, 1) IN ('+', '-') AND substr(updated_at, -3, 1) = ':'
      AND substr(updated_at, -5, 2) GLOB '[0-9][0-9]' AND substr(updated_at, -2, 2) GLOB '[0-9][0-9]'
      AND CAST(substr(updated_at, -5, 2) AS INTEGER) <= 23 AND CAST(substr(updated_at, -2, 2) AS INTEGER) <= 59
    ELSE substr(updated_at, -5, 1) IN ('+', '-') AND substr(updated_at, -4, 4) GLOB '[0-9][0-9][0-9][0-9]'
      AND CAST(substr(updated_at, -4, 2) AS INTEGER) <= 23 AND CAST(substr(updated_at, -2, 2) AS INTEGER) <= 59 END)
  AND (length(updated_at) = (CASE WHEN substr(updated_at, 17, 1) = ':' THEN 19 ELSE 16 END) + (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END)
    OR (substr(updated_at, 17, 1) = ':' AND substr(updated_at, 20, 1) = '.' AND length(updated_at) > 20 + (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END) AND substr(updated_at, 21, length(updated_at) - 20 - (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END)) NOT GLOB '*[^0-9]*'))
  AND CAST(substr(updated_at, 15, 2) AS INTEGER) <= 59
  AND (substr(updated_at, 17, 1) != ':' OR CAST(substr(updated_at, 18, 2) AS INTEGER) <= 59)
  AND (CAST(substr(updated_at, 12, 2) AS INTEGER) <= 23
    OR (substr(updated_at, 12, 2) = '24' AND substr(updated_at, 15, 2) = '00'
        AND (substr(updated_at, 17, 1) != ':' OR substr(updated_at, 18, 2) = '00')
        AND (instr(updated_at, '.') != 20 OR substr(updated_at, 21, length(updated_at) - 20 - (CASE WHEN substr(updated_at, -1) = 'Z' THEN 1 WHEN substr(updated_at, -3, 1) = ':' THEN 6 ELSE 5 END)) NOT GLOB '*[^0]*')))
  AND unixepoch(substr(updated_at, 1, 10) || ' ' || CASE WHEN substr(updated_at, 17, 1) = ':' THEN substr(updated_at, 12, 8) ELSE substr(updated_at, 12, 5) || ':00' END) IS NOT NULL;
--> statement-breakpoint
CREATE INDEX snapshots_instant_idx ON snapshots (instant_ms);
--> statement-breakpoint
-- Atomic canonical admission: an insert whose instant is already
-- stored is ignored inside the insert statement itself, so two
-- overlapping writes of one instant (in any spellings) can never
-- both land — a pre-insert SELECT alone cannot guarantee that.
-- Pre-existing legacy rows are untouched: the trigger constrains
-- only NEW inserts, and an ignored insert leaves the first stored
-- row (and its payload) exactly as it was.
CREATE TRIGGER snapshots_unique_instant BEFORE INSERT ON snapshots
WHEN NEW.instant_ms IS NOT NULL AND EXISTS (SELECT 1 FROM snapshots WHERE instant_ms = NEW.instant_ms)
BEGIN SELECT RAISE(IGNORE); END;
