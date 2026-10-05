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
