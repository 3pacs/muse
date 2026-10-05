# J1 — Event / Replay Policy (normalized)

One authoritative accepted event per `(ts, expiry)` identity, preserved
immutably across recovery and replay.

## Identity

- `ts` is the feed's own timestamp (`updated_at`/`quote_as_of`), normalized
  to canonical UTC ISO. Equivalent instants spelled with different offsets
  (`14:00+00:00` vs `10:00-04:00`) share one identity. The raw feed string
  is preserved as `ts_original`.
- Receipt clocks (`logged_at`) are metadata. They are never part of the
  semantic payload, the hash, or the identity.

## The accepted event

The complete normalized semantic payload = every `SNAP_COLS` field,
canonicalized (`event_core()`), plus the strike map (`gex_m`) and the
formula/units tag (`gex_formula`, R6). The journal (`maxpain_history.jsonl`)
is the authoritative record; the strike map is embedded in each journal
record so every projection can be rebuilt after restart. The DB is a
projection of accepted events, never a second source of truth.

## One decision, three callers

`classify_event()` in `tape_db.py` is the single duplicate/conflict
decision used by the logger, `mirror_record()`, and `backfill()`:

- no stored event → **new** (accept; write all projections)
- same identity, equal canonical core → **duplicate** (no-op; converge any
  missing projection from the ACCEPTED event)
- same identity, changed core — or same core with a changed strike map →
  **conflict** (quarantine receipt in `mirror_conflicts` with a reason;
  the accepted event stands; the rejected payload never adds a strike or
  becomes a projection)

The logger validates the incoming payload against the accepted event;
presence flags alone never decide. On conflict the logger first repairs any
missing projection from the accepted event, then receipts the incoming
attempt.

## Legacy rows

`payload_hash = NULL` rows are NEVER adopted blindly. The stored content is
reconstructed (snapshot row + strike map), canonicalized, and compared:
equal → duplicate (hash filled in, validated); different → conflict.

## Dry-run parity

`backfill(dry_run=True)` evolves a `ReplayState` overlay over the DB so it
simulates exactly what the real run does — intra-file duplicates (A,A),
conflict sequences (A,C,B,A), malformed lines, partial strike overlaps —
without writing. Dry counts equal real counts.

## Out of scope (reported open)

R1-A solver numerics (close/off-grid roots, raw precision, degeneracy
reasons), R5/R7 interpreter admission, and dashboard timestamp/formula
projection stay as the reviewer left them.

---

## J1-B — completion of accepted-event replay/recovery (2026-10-05)

J1-B closes the ten boundary fixtures the red team returned after
verifying J1. Scope stays `maxpain_log.py`, `tape_db.py`, focused
committed offline tests, and this policy.

### Explicit vs unavailable strike maps

A strike map is **explicit** when it is provided: a feed `by_strike` list
(even `[]`), a journal record's `gex_m` key (even `{}`), a `mirror_record`
`gex_m` argument, or a non-empty DB strike projection. It is **unavailable**
when the source is silent (missing key, no projection).

- Explicit vs explicit: strict equality. Deleting a nonempty accepted map
  (explicit `{}`) is a changed payload → conflict. The logger and direct
  `mirror_record` apply the same verdict.
- Either side unavailable: the map is no opinion; the core decides.
- Accepted map unavailable + incoming explicit: cannot verify → quarantine
  the incoming, do not guess or silently adopt. Legacy records without
  complete accepted content stay explicitly unverified under this additive
  compatibility policy.

### Secondary records validate against the parent

A strike-file line is admitted only against an accepted parent event:

- No accepted event for the identity → **orphan**: quarantined in
  `mirror_conflicts`, never accepted independently.
- Parent accepted but its map undefined (no embedded map, no DB strikes,
  no earlier line) → the line **defines** the map → accepted.
- Parent map defined → the line must match it exactly: any value change,
  disjoint addition, subset, or formula change is a **conflict**. A
  rejected payload never supplements the accepted map.

Formula/units lineage is semantic: the same strike value with a changed
`gex_formula` is a conflict, not a duplicate.

### Full semantic hash

`semantic_hash(core, strike_map)` covers the canonical core plus the
strike map. Stored `payload_hash` values and conflict receipts (`kept`,
`incoming`) use it, so a strike-only change yields distinct hashes. Receipt
clocks remain excluded; `ts` remains normalized.

### Embedded map rebuilds projections

The journal's embedded accepted map is sufficient to rebuild secondary
projections: `backfill()` writes the embedded strikes on snapshot accept
(no separate strike file needed), and the logger's convergence repairs a
missing DB strike projection from accepted content independently of
snapshot presence. Missing strikes are inserted; the accepted event is
never rewritten and extra rows are never deleted.

### Canonical identity in every writer

`insert_snapshot()` and `backfill()` persist the canonical UTC `ts`. The
raw original spelling is preserved separately in the journal
(`ts_original`). Pre-existing offset-spelled rows converge additively;
history is never rewritten and no silent duplicates are created.

### Unterminated tails and non-object lines

Appends after an unterminated journal tail are framed: if the file does
not end with a newline, the incomplete tail is terminated first so the new
event stays independently parseable. Raw bytes are preserved; history is
never rewritten. Valid JSON that is not an object (scalar/list) is
rejected with a count/reason; replay continues with subsequent lines.
Dry-run and real replay produce identical verdicts and counters, with no
writes in dry-run.

### Open (out of scope for J1-B)

The twelve numerical/provenance/dashboard failures from the earlier
20-case extension remain explicitly open: R1-A solver numerics, R5/R7
interpreter admission/provenance, and dashboard projection checks. No
assertion was weakened to claim closure.

---

## J1-C — durable complete-event admission and truthful reconciliation (2026-10-05)

J1-C closes the eight continuity contracts the red team returned after
verifying J1-B. Scope stays `maxpain_log.py`, `tape_db.py`, committed
offline tests, and this policy.

### Persisted semantic content

The `snapshots` row now persists, alongside the canonical core:

- `gex_units` — the actual units lineage (e.g. "USD millions per 1% spot
  move"). Units are semantic: the same values with incompatible units are
  a conflict, never a duplicate. `gex_units` is part of `SNAP_COLS`, hence
  of `event_core()` and the semantic hash.
- `gex_map_status` — `explicit` / `explicit_empty` / `unavailable`.
  Written by `mirror_record()` and `insert_snapshot()`; added to existing
  DBs by a compatibility `ALTER TABLE`. Rows predating the column report
  `unavailable`. The status is authoritative: an explicitly empty map
  survives restart and can never acquire strikes from a secondary line;
  a lost nonempty projection is an integrity mismatch, never a verified
  duplicate of an explicitly empty incoming map.

Legacy rows without the new columns are never rewritten.

### One complete-event verdict

`_classify_snapshot_line()` now compares the full journal event,
including the embedded strike map, exactly as direct mirror does. A
primary journal row with a changed embedded map conflicts. Projection
loss is distinguished from change: an embedded map that is a strict
superset of the stored projection (with overlapping values equal) is a
duplicate whose missing strikes are repaired from the journal — the
journal is authoritative.

### Truthful reconciliation

Backfill reconciles duplicate journal events, not just new ones: on a
duplicate snapshot with an embedded map, absent DB strike rows are
reinserted from accepted content (dry-run and real agree; dry-run never
writes). The logger's convergence verifies the DB snapshot projection
against the accepted journal event; divergent values are repaired from
the journal with an explicit "integrity repaired" note, never a false
"already logged".

### Legacy timestamp aliases

Pre-normalization rows (written by old code with raw offset spellings)
are resolved additively at read time: `_resolve_identity()` first tries
the canonical ts, then scans the expiry's rows for one normalizing to
the same instant. Raw history is never rewritten and no silent second
identity is inserted; an equivalent instant replays as duplicate (or
conflicts if the payload changed) with a receipt.

### Open (out of scope for J1-C)

The twelve numerical/provenance/dashboard failures remain open per the
reviewer: R1-A solver numerics, R5/R7 interpreter admission/provenance,
dashboard projection checks. No assertion was weakened to claim closure.

## J1-D — prove accepted content before repair (2026-10-05)

J1-D replaces the J1-C superset heuristic with digest-based proof of
original accepted content.

### Accepted payload digest

The full semantic digest (`payload_hash`, covering core + embedded map)
is retained at accept time and verified before any repair. A duplicate
journal line must prove it is the original accepted payload via digest
match; a different payload (including a later superset or growth from
an explicitly empty map) is a conflict, not a repair. Legacy rows
without a digest fall back to exact map comparison; an explicitly empty
stored map can never grow.

### Ambiguous legacy aliases

`_resolve_identity()` now detects multiple distinct rows normalizing to
the same instant. If they agree on content, the first is returned; if
they differ, `_AMBIGUOUS` is returned and callers quarantine (conflict)
rather than arbitrarily resolving. The same resolution is used in
`fetch_stored`, `rec_from_row`, payload-hash lookup, mirror, snapshot/
strike projection writes, and logger fallback.

### Logger integrity

The logger propagates source-reported `gex_units` from the feed to the
accepted record (unknown stays unknown). On duplicate, the logger
verifies DB strike projection values against accepted content, not just
missing keys — divergent values are repaired via UPDATE with an explicit
"integrity repaired" note. If direct mirror returns conflict/quarantine,
the logger never appends the incoming payload as accepted history; it
restores only the accepted legacy content or retains an explicit
unavailable/integrity state.

### Verification

8/8 J1-D fixtures, 10/10 J1-B, 8/8 J1, 21/21 original controls, 5/5
probes, 35/35 committed replay tests (27 prior + 8 new J1-D). The twelve
out-of-scope failures remain explicitly open.

## J1-E — finish proof across every recovery path (2026-10-05)

J1-E closes the ten proof-extension contracts.

### Full alias comparison

`_resolve_identity()` now compares the full canonical core plus strike
map/status for every alias candidate. Matching spot/formula alone is
insufficient — any difference in core fields or map values yields
`_AMBIGUOUS`, which callers quarantine. Ambiguity propagates to reads,
hash lookups, writers, and logger; the logger never appends incoming
content after mirror conflict or unresolved ambiguity.

### Digest proof

A present stored digest must match the incoming full digest. A mismatch
is proof of tampering — conflict, not a fallback to map comparison.
The exact-map legacy fallback applies only when the digest is truly
absent (NULL). `mirror_record`, backfill, and logger all enforce this.

### DB-only recovery

When the journal is missing and the DB is the fallback, the logger
verifies the DB projection against the retained digest before accepting
it. A digest mismatch quarantines; the tampered projection is never
adopted and the incoming feed is not appended.

### Value and formula repair

Backfill and logger repair divergent strike values (not just missing
keys) via UPDATE on the resolved actual ts — never a zero-row UPDATE
with a false success message. Formula lineage is verified alongside
values; divergent formulas are repaired from accepted proof.

### Unavailable maps

An unavailable accepted map cannot silently adopt a later map. Without
proof of original content, the incoming is a conflict.

### Units lineage

Primary (journal) and secondary (gex.jsonl) projections both carry the
exact source-reported `gex_units`. No hardcoded defaults.

### Verification

10/10 J1-E fixtures, 8/8 J1-D, 10/10 J1-B, 8/8 J1, 21/21 original
controls, 5/5 probes, 45/45 committed replay tests (35 prior + 10 new
J1-E). The twelve out-of-scope failures remain explicitly open.
