# MAIN producer evidence handoff — MUSE-MAIN-PRODUCER-CONTRACT-20261020 (completion of the ACK evidence)

Companion to the MAIN producer ACK (PR #2 comment 6303374031, recorded as RECEIVED at docs `cd4af20e`). This folder supplies the minimal remaining handoff the verification asked for: the sealed interpreter copy that matches the asserted live hash, a pinned machine-readable schema, and the existing captured price-only envelopes/records with capture identity. Everything here is from retained source/captures — no new provider polling, no new backend writer, no fabricated bars or volume.

## Source linkage — resolved

- `interpreter.py` in this folder is the **existing sealed byte copy** (seal of 2026-10-19, seal manifest file SHA-256 `6f8c1cd9d26f64813bfb43d44e4790c0304fe8a14d99d0d0755d8e4deafd24b2`), SHA-256 **`b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e`** — identical to the live producer source asserted in the ACK. The repository's older copies (`implementation/pipeline/interpreter.py` `e4f34786…`, repository-root `interpreter.py` `6f6d4ae0…`) are earlier revisions and are **not** the live source; the other three ACK pins (`indicator_tracker.py` `8f50ab4a…`, `tape_db.py` `9031b67d…`, `maxpain_log.py` `0b34acc4…`) match the packaged pipeline files exactly, as the verification found.
- Placement note (owner's choice, per the operator's instruction to follow this codebase's own pattern): this repo carries pinned source and receipts as files in evidence folders; the sealed copy is published here as that reference rather than only by hash. This is a source reference for the ACK — it is not a deployment, and the sealed `/gex/` serving lane remains separately held.

## Symbol / config binding

The producer's configured instrument is **SPY only**: the pinned interpreter builds the snapshot from the SPY 0DTE chain (3 real-time strikes + 143 Nasdaq delayed strikes, `src_mix` in the retained record). No QQQ positioning is produced anywhere in this system; QQQ appears only as transient indicator events outside this envelope. Price unit is USD; `spot` is the SPY spot price at producer build time.

## Files in this folder

| File | SHA-256 | What it is |
| --- | --- | --- |
| `interpreter.py` | `b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e` | Sealed byte copy of the live producer source (feed producer). |
| `feed_all.schema.json` | (see captures.json) | Descriptive JSON Schema of the `GET /feed/all` envelope at the pin above; generated from the supplied capture below and verified against it. |
| `envelope-ok-afterclose-20261020.json` | `53f0f4c6e5a91ac7592b7338fbef353e7ec06e90914d82f247c478009d173380` | Full captured envelope, producer healthy, session closed: captured 2026-10-20T21:29:16Z, `status "ok"`, `market_open false`, spot 771.2 (after-hours quote). |
| `healthy-session-record-20261020.json` | (see captures.json) | Last market-open producer cycle of 2026-10-20 in storage form (tape.db `snapshots` row): `ts 2026-10-20T19:56:46.296471+00:00`, spot 768.49, max pain 768, `payload_hash f38b96701502a42ffd5c73922a39a93c30b4ab96de81de44ee653d626a1f4791`, `quote_as_of 2026-10-20T19:56:27+00:00`, `src_mix "3 rtd + 143 nasdaq_delayed"`. **Declared:** the full JSON envelope for this cycle was not retained; the retained identity is this row plus its payload hash. |
| `captures.json` | — | Machine-readable manifest of the captures above (identity, hashes, capture clocks, state). |

## Failed / stale envelope — what exists, declared exactly

No verbatim full JSON file of a failed envelope was retained. The failed state is evidenced by the producer's own retained records of 2026-10-20, 09:42–09:47 PT: the watcher/logger observed `/feed/all` returning `status "error"` payloads with all data fields null (payload `updated` values 16:43:25Z, 16:44:49Z, 16:46:55Z; watcher output `FEED_ERROR | timed out`) while the interpreter process stayed alive under its supervisor; the append-only history simply has no records for those cycles, and the last successful record before the window was 16:40:50Z (spot 769.47, max pain 768). At the pinned source, the error envelope's shape is: `status "error"` with the data fields null — the consumer must treat any non-`ok` status as no-data (as the C06/C07 responses already do). The after-close envelope above is the retained stale-session state (`market_open false` is data, not an error).

## Clock ownership (no clock substitutes for another)

| Clock | Owner / meaning |
| --- | --- |
| `updated_at` (envelope) / `ts` (stored snapshot) | **Producer build time** — when the interpreter built the snapshot (UTC ISO-8601). This is the first-known/receipt time of the snapshot content at the producer. |
| `quote_as_of` | **Source quote clock** — the RTD provider's quote time as reported to the producer; may precede `updated_at`. It is not an exchange bar-close time; no bar-close/event-interval clock exists in this producer (**unavailable**, declared in the ACK). |
| `sources.nasdaq.as_of` | The delayed-wing source's own as-of time (~15-min delayed Nasdaq data), labelled with `delay "~15min"` beside the RTD `delay "realtime"`. |
| Consumer receipt / evaluation clocks | Owned by the consumer at its own observation time; the producer asserts nothing about them and they must not be back-filled from `updated_at` or `quote_as_of`. |

## Semantics carried from the ACK (unchanged)

- **Duplicates/conflicts:** snapshots are stored under `UNIQUE(ts, expiry)`, history append-only; a conflicting same-`ts` re-delivery is recorded in `mirror_conflicts` (`kept_hash`, `incoming_hash`, `received_at`) and never silently merged or overwritten.
- **Ordering:** receipt order by `ts` only. No revision sequence, retraction, or bar ordering exists or is implied.
- **Continuity:** gaps are honest absences (see the failed window above); nothing is backfilled or interpolated.
- **Missing fields:** completed one-minute OHLCV (open/high/low/bar close/share volume), bar event intervals, completion/finality, and a versioned exchange calendar are **missing/unsupported** per the ACK matrix. Option-contract volumes in the envelope are contract counts, never share volume; quote counts are never used as volume.

**C07 linkage:** the coherence revision referenced by this handoff is delivered at implementation pin `29817f052543f91bf1a978daa1f60439bd2df298` (delivery comment 6303372437; coherence comment 6304572745), awaiting independent re-verification.
