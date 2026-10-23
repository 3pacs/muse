# MAIN producer packet — rev3: sources coverage (provider key + unknown clocks)

Evidence/docs-only revision answering the consolidated review at docs `6e22de72`. Rev2's fixes are verified and stand (meta-schema validity, status variants, corrected clocks, 15/15 reproduced independently); rev3 closes the three remaining source-to-schema coverage gaps the reviewer's probes found. **Producer source unchanged** — pin `b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e`. Retained captures byte-identical. C07 VERIFIED/CLOSED, untouched.

## The three gaps and the corrected policy

At the pinned source, `sources` is built as `{<chain_provider>: chain_src, "nasdaq": {...}}` — the first key is the chain's **own provider name**, and either entry's `as_of` is the provider/cache timestamp **or null**. Rev2 required the literal key `rtd` and string `as_of` on both entries, rejecting three shapes the source genuinely emits:

1. **Nasdaq wings unavailable** — `sources.nasdaq.as_of: null`, `n_strikes: 0` (cache not yet populated / failed-empty). Now admitted.
2. **Chain/quote timestamps absent** — the chain entry's `as_of: null` beside the already-allowed top-level `quote_as_of: null`. Now admitted under one consistent policy.
3. **Alternate chain provider** — e.g. `sources: {"vendor_delayed": {...}, "nasdaq": {...}}` with `n_strikes_rtd_live: 0`. Now admitted: `sources` requires the fixed `nasdaq` entry and admits **one dynamic provider key** whose entry carries its own `as_of` / `delay` / `n_strikes` (plus optional `time_note`).

**Unknown-clock policy (explicit):** a null `as_of` means that source's clock is **unknown** — it stays unknown. It is never guessed, never replaced by `updated_at`, `quote_as_of`, or the consumer's receipt clock, and source-age metrics derived from it are unavailable, not estimated.

**Provenance policy (explicit):** the provider key and its declared `delay` are the provenance. A delayed chain is **never presented as realtime** (the source's own R7 rule, now contractual): consumers take delay/realtime character from the entry itself, and `n_strikes_rtd_live` counts only strikes whose source is the live provider — 0 under a delayed chain, as the source reports it.

## Identity binding (b95d vs cb4f)

Two distinct source identities are now in play and must stay separately bound in every receipt:

| Pin | Identity | Role |
| --- | --- | --- |
| `b95d1c3c73f720fe71fa139a7964af118fa139dea344fbdb7fa42dbd4619406e` | Live producer on the Muse VM (sealed copy in the rev1 folder) | The contract source for this packet's schema; what MAIN runs and what the captures came from. |
| `cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0` | Public-safe variant in `docs/muse-gex-deploy-20261020/` | The proposed `/gex/` deployment payload: same envelope shapes (the provenance/sources expressions are the same), distinct public error/signal/serialization screening. A serving receipt must name cb4f, never b95d. |

## Checks

`prove_schema.py` + `schema-check-receipt.json`: **18/18** — all 15 rev2 checks preserved and passing, plus the three boundary cases above (null nasdaq `as_of`, null chain `as_of`, alternate provider key), each admitted as data with its provenance/clock limits intact and non-ok withholding unchanged.

## Files

| File | Role |
| --- | --- |
| `feed_all.schema.json` | Corrected contract (supersedes rev2 schema `eac803a2…` for the `sources` block; all other variants unchanged). |
| `prove_schema.py` / `schema-check-receipt.json` | Offline checks + bound receipt (18/18). |
| `envelope-ok-afterclose-20261020.json` / `healthy-session-record-20261020.json` | Retained captures, byte-identical (`53f0f4c6…` / `0a9862d6…`). |
| `manifest.json` | Hashes binding this revision, the rev2 packet it corrects, both source identities, and the preserved captures. |
