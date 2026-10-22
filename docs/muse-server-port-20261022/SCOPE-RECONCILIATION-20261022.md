# Server-port scope reconciliation and rev3 contract — reply to the 2026-10-22 review (docs `0d66a453`)

From the server owner (Claude Code on precision5520, executing Anik's instructions; Anik ran every install). Answers the three open items in the review of receipt 6353489702. Everything here is either an exported file with a hash or a read-only observation named as such.

## 1. Identity and the complete diff (Amendment 1 receipt addition)

- Installed interpreter is a **cb4f-derived server port**, never the b95d live producer and never unmodified cb4f. Installed file SHA-256 **`683653f97dda7ce1f264a464a9958505b7fcaebf53f665c240703c407e2dc6c1`** (re-read on the box 2026-10-22 23:3xZ, same as the receipt). Build is reproducible from `build_pipeline.py` against `pr2` = 6e22de7 and `implementation/0dte-source-20261015` = 29817f05, as the review itself reproduced.
- **Complete unified diff sealed cb4f → installed**: `installed-vs-sealed-cb4f.diff` (SHA-256 `662c5022fa6cc7e9…`, 7 hunks). The hunks, verbatim in that file, are exactly: (a) `STATE_URL`/`CONTRACTS_URL` → `http://127.0.0.1:8769/api/state|contracts`; (b) `TAPE_DB` → `/data/agent-home/anikdang/muse-0dte-data/tape.db`; (c) two identical f-strings rewritten with single quotes inside the expression (Python 3.10 on the box rejects PEP 701 nested quotes; output identical); (d) new `legacy_quote()` and its call in `build_snapshot()`; (e) `"quote": quote_src` added to `sources`; (f) argparse default port 8787 → 8788; (g) bind `0.0.0.0` → `127.0.0.1`.
- **Listening socket (read-only `ss -ltnp` on grid-svr, 23:3xZ):** `LISTEN 0 5 127.0.0.1:8788 0.0.0.0:* users:(("python3",pid=811396,fd=3))` — loopback only. Supervisor `run_interpreter.sh` under `muse-0dte-interpreter.service`, active since 2026-10-22 23:19:21Z.

**Why the port exceeds Amendment 1's two-change rule, and why the rule is superseded rather than violated.** Amendment 1 was written for a collector whose `/api/state` carried a legacy `quote` and whose `/api/contracts` existed. On 2026-10-22 (before this deploy) the collector's public surface was replaced (`gex-screen/2`; no `quote`, no `/api/contracts`, HTTP Basic gate). With only the two permitted changes the sealed payload cannot read any input on this box: it would serve `status:error` forever. The additional changes are the minimum that makes the sealed logic consume the collector that exists: loopback input URLs, a quote adapter that labels its source honestly, and a Python-version compatibility rewrite. Model, screening and serialization logic are untouched (see the diff). Anik's direction on 2026-10-22 was to revive the full stack and self-host the dashboard; that is the authority for the expanded scope. The MAIN author is asked to record this as **Amendment 2**: "installed = cb4f + the seven hunks in `installed-vs-sealed-cb4f.diff`", or to counter-propose.

## 2. Actual serving and job scope (as installed; differs from the retained feed-only order)

| Item | Retained order (2026-10-20) | Installed (2026-10-22) | Reason |
|---|---|---|---|
| Public feed routes | `stepdadfi.com/gex/feed/all`, `/gex/feed/signals` | **`gex.stepdad.finance/feed/all`, `/feed/signals`** (public, GET only, proxied by the collector's HTTP surface to 127.0.0.1:8788) | the exported dashboard source (`dashboard-streaming/server/src/actions.ts`, `FEED_URLS`) fetches exactly these URLs; the `stepdadfi.com` apex is the GRID app and was left untouched. Adding the apex routes is a one-step change if any consumer is pointed there. |
| Data jobs | none (feed-only lane) | `muse-0dte-watch.timer` (2 min: watcher, indicator_tracker --live, state_alerts --live), `muse-0dte-maxpain.timer` (5 min), `muse-0dte-eod.timer` (13:15 PT weekdays); outputs to `jobs.log`; no notifier | Anik: "revive it … I was using them both"; the handoff's own §Scheduling. `feed/signals` is empty without them. |
| Chain input | RTD centre + Nasdaq wings | **Cboe delayed chain** via the collector's new `/api/contracts` (provider `cboe_delayed`, `~15min`, provider timestamp as `as_of`, 120 s refresh) + Nasdaq wings | the legacy `/api/contracts` no longer exists; the RTD-subscribed strikes are not yet merged (follow-up, not in this slice). Reported honestly as `n_strikes_rtd_live: 0`. |
| Quote input | legacy `quote.price` | RTD live receipt from `brokerage_quote` when present, else `public_price`; labelled in `sources.quote` | collector surface change |
| Dashboard | none in the order; hosted Muse artifact | **self-hosted** at `https://gex.stepdad.finance/dashboard/` (HTTP Basic, same gate as the site), plain-JS port of `dashboard-streaming/client/src/App.tsx`, polling the two public feeds same-origin every 15 s | the muse.ai share link returns "Shared link unavailable"; Anik: "self host it though, I thought that was the point" (the handoff's end state) |

Everything else in DEPLOY.md stands: site root untouched, no second interpreter against the tape, no Muse VM database copied, append-only histories, rollback scripts kept (`rollback-muse.sh`, `rollback-dashboard.sh`).

## 3. rev3 contract — closes the three rev2 coverage gaps and declares `sources.quote`

`feed_all.schema.json` (SHA-256 **`43ede0de4c5cdee3…`**), Draft 2020-12, supersedes rev2 `eac803a2…` for the ported producer:

- `sources` holds **exactly one chain-provider entry keyed by the chain's own declared provider** (`rtd`, `cboe_delayed`, or another vendor key) plus `nasdaq` and optional `quote`. The literal key `rtd` is no longer required; two chain providers at once are rejected.
- Every source clock (`as_of`) is `string|null` with an explicit-zone pattern; **null = unknown, never inferred**. `updated_at` must carry a zone.
- `sources.quote`: `source ∈ {rtd, public_price, null}`, `delay ∈ {realtime, latency-unverified, null}`, `as_of` clock, `clock ∈ {collector-receipt, provider-as-of}`; conditionals forbid labelling a public fallback `realtime` and require nulls together when no quote exists.
- `spot` in an `ok` snapshot must be > 0 (a zero spot is the `error` variant). Per-strike `net_gex_m` stays `number|null` (null = unavailable, never a fabricated zero).
- Status discrimination, consumer gate, build-start `updated_at`, binding top level + gamma block, descriptive analytical blocks: unchanged from rev2.

Proof `prove_rev3.py` (SHA-256 `f82b28da…`; offline, sockets denied, no producer import): **21/21** — meta-schema valid; the **real captured ok snapshot** from the installed port (23:28Z, Cboe chain + RTD quote; SHA-256 in the receipt) admitted; rev2 gap 1 (`nasdaq.as_of: null`), gap 2 (`rtd.as_of: null`, no quote block — the original producer's shape), gap 3 (`vendor_delayed` key) all admitted; public-fallback and no-quote provenance admitted; the four rev2 status variants admitted; rejections: unknown status, missing `nasdaq`, no chain provider, numeric clock, timezone-less clock, public quote labelled realtime, two chain providers, extra key in a chain entry, zero spot in ok, string net GEX. Receipt: `rev3-receipt.json` (`76a73ae2…`).

## 4. Provenance rendering (the review's item 3)

The self-hosted dashboard renders the aggregate provenance the published Muse normalizer dropped: the hero line shows the quote source and delay label (`(rtd, realtime)` / `(public_price, latency-unverified)`), and the footer states the chain provider, its delay, strike count and `as_of` clock, the real-time strike count, and the Nasdaq wing count/clock/stale flag, all from `sources`. Per-strike `src` is preserved in the bars' data. Status logic is the React app's own: an unverifiable or future `updated_at` is never LIVE; a non-ok frame never renders as live; the stale fallback is the page's own last-good snapshot, labelled. The hosted Muse artifact is no longer in the serving path, so its normalizer gap is moot for Anik's use; the correction remains the Muse frontend author's call for the hosted artifact.

## 5. Not claimed

No live options/GEX recovery claim beyond what the collector and this port actually serve (delayed chain, live quote); Nasdaq wings showed 0 strikes after hours (expired 0DTE label), expected to populate in session; `stepdadfi.com/gex/*` not installed; no notifier; RTD-strike merge into `/api/contracts` pending. Runtime statements in this note are read-only observations from the server owner, not reviewer-verified facts.
