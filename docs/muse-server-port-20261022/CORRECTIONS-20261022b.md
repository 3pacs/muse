# Corrections after review d60eeb7e (server-port rev3 + self-hosted frontend)

Gex export commit: `5c861f4` (paths `stopgap-20261022-muse/contract-rev3/`, `stopgap-20261022-dashboard/page/`).

1. **Exactly-one-chain rule independent of `quote`** — `sources` now uses `if required[quote] then maxProperties 3 else maxProperties 2` (plus the existing no-chain `not`). New negatives: two chain providers without quote → rejected; one chain without quote → admitted.
2. **Clock kind bound to the quote source branch** — `public_price` requires `clock: provider-as-of` (collector-receipt rejected; missing clock kind rejected); `rtd` clock, when stated, must be `collector-receipt` (legacy RTD quote without clock kind stays admitted — never guessed); `source: null` forbids a clock kind.
   Proof `prove_rev3.py`: **28/28** (owner 21 preserved + 7 new), receipt `rev3-receipt.json`.
3. **Frontend quote-clock explanation** — hero and footer now say `quote collector receipt <time> PT` or `quote provider as-of (latency unverified) <time> PT`, or `clock kind not stated` for a legacy RTD quote, from `sources.quote` only; the chain line says `provider as-of` for the chain clock.
4. **Frontend generic chain provider** — `chainSource()` selects the single declared entry other than `nasdaq`/`quote`; two entries or none → null (never assigned to RTD). Pure-view test adds the `vendor_delayed` case and the clock-label cases.

Deployment of the corrected `dashboard.js` to the self-hosted page is a separate operator step (owner-reported when done). No producer, schema-consumer, provider or runtime change beyond these files.
