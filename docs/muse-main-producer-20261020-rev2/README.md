# MAIN producer packet — rev2: corrected schema / status / clock contract

Evidence/docs-only revision of `docs/muse-main-producer-20261020/` (packet at `6c8eabbe`), answering the integration review at docs `ed91cb7c`. **The producer source is unchanged** — pin `b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e` stands, the sealed copy in the rev1 folder remains the immutable source reference, and no producer code was changed or redeployed to make this contract agree with it. Retained capture bytes are preserved byte-identical (hashes below). C07 remains VERIFIED/CLOSED and untouched.

## What was wrong and what changed

1. **The rev1 schema was invalid and wrong.** Its generator inferred types from the single after-close capture: it emitted a duplicate `["null","null"]` type for `gamma.put_wall` (not valid Draft 2020-12 — `check_schema` rejects it) and froze `put_wall` as null-only, rejecting the source's real number-or-null output. Rev2's `feed_all.schema.json` is hand-built from the pinned source's return statements and passes `Draft202012Validator.check_schema` (see the offline receipt).
2. **Status variants are now source-backed.** The producer emits four `/feed/all` shapes, and the schema discriminates them by `status` const:
   - `ok` — the full snapshot (15 top-level keys; gamma block binding, walls/flip/max_pain **number-or-null**).
   - `error` — **two source shapes, one variant:** the sparse poll-exception object `{status, error, updated_at}` (all other data fields **absent, not null**), and the no-quote object, which adds `market_open`, `spot: 0`, `expiry`. (Rev1's README phrase "all data fields null" was wrong for this producer and is corrected here: the fields are absent; a consumer reading them gets "missing", and must gate on status first.)
   - `quarantined` — future-quote rejection: `{status, quarantine_reason, updated_at, market_open: false, quote_as_of}`.
   - `starting` — pre-first-poll: `{status, updated_at: null}`.
   An unlisted status validates against **no** variant, so schema admission can never substitute for the consumer's `status == "ok"` gate; that gate is stated in the schema description and exercised in the checks (a full ok body relabeled `error` is schema-valid as the error variant and still withheld from interpretation).
3. **Clock declarations corrected.** Rev1 called `updated_at` a first-known/receipt time. At the pinned source, `build_snapshot()` assigns `now` at **build start, before its fetches** — in the retained capture `updated_at` is `21:29:16.142252Z` while the Nasdaq acquisition stamp inside the same envelope is `21:29:31.443624Z`, ~15.3 s later. `updated_at` therefore cannot represent receipt of the completed content, and nothing in this packet treats it as one.

## Clock ownership (corrected)

| Clock | Owner / meaning |
| --- | --- |
| `updated_at` | **Producer build-start time** — stamped when the snapshot build begins, before source fetches complete. It bounds content freshness from *before* the build, never from completion. |
| `quote_as_of` | **Forwarded source quote clock** — the RTD provider's quote time as reported to the producer; may precede `updated_at`. Not an exchange bar-close time. |
| `sources.nasdaq.as_of` | **Cache acquisition timestamp** for the delayed wing, declared beside its `delay "~15min"` (RTD entry: `delay "realtime"`). It is when the producer acquired the delayed data, which can be *after* `updated_at`. |
| Completed-response receipt / evaluation clocks | **Consumer-owned**, observed by the consumer when the finished response arrives / is evaluated. The producer asserts nothing about them. |
| Event / bar-close time | **Unavailable** in this producer — absent, never substituted by any clock above. |

## Scope and semantics (unchanged, restated)

- Scope of the schema: a **price/status contract**. The top level and gamma block are binding; `flow`, `vanna_charm`, `iv`, `positioning` are declared as objects whose detailed fields are descriptive (capture-typed), not a frozen analytical schema.
- Symbol binding: **SPY only**. Price unit USD; option volumes are contract counts, never share volume.
- Ordering by `ts`; same-`ts` conflicts recorded in `mirror_conflicts`, never merged; gaps are honest absences, never backfilled.
- Historical raw failure capture: **UNAVAILABLE** (unchanged declaration — not reconstructed). Failure shapes are tested with explicitly labeled synthetic fixtures derived from the pinned source text (`prove_schema.py`), which are contract fixtures, not market evidence.

## Files

| File | Role |
| --- | --- |
| `feed_all.schema.json` | Corrected contract (supersedes rev1 schema `19513e20…`, which was invalid). |
| `prove_schema.py` | Offline checks: meta-schema validity, captured-ok validation, labeled synthetic timeout/no-quote/quarantine/starting fixtures, numeric/null walls, unknown-status rejection, status-gate withholding. |
| `schema-check-receipt.json` | Bound result of the checks above (15/15) with input hashes. |
| `envelope-ok-afterclose-20261020.json` | Retained capture, byte-identical to rev1 (`53f0f4c6…`). |
| `healthy-session-record-20261020.json` | Retained storage-form record, byte-identical to rev1 (`0a9862d6…`). |
| `manifest.json` | Hashes binding this revision, the rev1 packet it corrects, and the preserved producer pin. |
