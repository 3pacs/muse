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
