# DEPLOY AMENDMENT 2 — MAIN reconciliation of the reviewed self-hosted server port

**Issued by MAIN, the coordination/order owner, on 2026-10-23; recorded through the retained single-writer PR2 handoff at MAIN's explicit direction. Scope decision: CLOSED.** MAIN accepts the already reviewed server-port and self-hosted scope below as the named reconciliation of the October 20 order. No further MAIN takeover, owner search, counterproposal or duplicate implementation is pending for this decision.

This is an **additive amendment**. [DEPLOY.md](DEPLOY.md), [Amendment 1](DEPLOY-AMENDMENT-1.md), their original publications and historical receipts remain unchanged. For the named baseline only, this amendment supersedes their conflicting one-/two-change allowance, historical route selection and feed-only non-goals. It records the reviewed scope and its evidence limits; it is not a new deployment, rollback, trading, credential, authentication, provider-polling or scheduling instruction.

## Bound baseline and evidence

The owner packet is immutable **[e407fbde8cbb51147e5104863e9dd80a44ead747](https://github.com/3pacs/muse/tree/e407fbde8cbb51147e5104863e9dd80a44ead747/docs/muse-server-port-20261022)**. Its [scope/deviation table](https://github.com/3pacs/muse/blob/e407fbde8cbb51147e5104863e9dd80a44ead747/docs/muse-server-port-20261022/SCOPE-RECONCILIATION-20261022.md) explains the replacement collector surface and self-hosted path. Its original rev3 schema/proof wording is historical; [CORRECTIONS-20261022b.md](https://github.com/3pacs/muse/blob/e407fbde8cbb51147e5104863e9dd80a44ead747/docs/muse-server-port-20261022/CORRECTIONS-20261022b.md) and the packet's corrected bytes define the accepted rev3b contract.

| Identity | SHA-256 / immutable pin |
| --- | --- |
| Sealed public-safe cb4f base | `cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0` |
| Reviewed cb4f-derived server port | `683653f97dda7ce1f264a464a9958505b7fcaebf53f665c240703c407e2dc6c1` |
| Complete seven-hunk diff | `662c5022fa6cc7e9795725df9866c40a8c8f92643ccea057d5a07444b569ed0b` |
| Corrected port schema | `5a93b50ad13c34d3c9edd922df31e119ae37ae40f773fe15f4479cb92466092d` |
| Corrected self-hosted dashboard JS | `4f98536fe82b6ffa350da06741f29124e9fb5259bf277c97741767a69423f65f` |
| C07 implementation, still closed | `29817f052543f91bf1a978daa1f60439bd2df298` |

The [complete diff](https://github.com/3pacs/muse/blob/e407fbde8cbb51147e5104863e9dd80a44ead747/docs/muse-server-port-20261022/installed-vs-sealed-cb4f.diff) was independently reproduced exactly from retained cb4f and ported files. Its seven hunks are: local collector state/contracts URLs; server `TAPE_DB`; two Python 3.10 f-string compatibility rewrites in one hunk; `legacy_quote()` plus its snapshot call; `sources.quote`; default port 8788; and literal bind `127.0.0.1`. These define this port's interpreter delta. It is neither the b95d live producer nor unmodified cb4f. This allowance does not extend to unspecified future source changes.

## Reconciled deviations from the October 20 order

| October 20 order / Amendment 1 | MAIN's recorded baseline | Evidence and limit |
| --- | --- | --- |
| Only `TAPE_DB`, then `TAPE_DB` plus bind | cb4f plus exactly the published seven hunks | Full source/diff reproduced; the two-change rule is superseded for this identified port |
| Collector URLs on the public hostname; legacy quote shape | Loopback collector `127.0.0.1:8769/api/state` and `/api/contracts`; receipt-aware quote adapter | Independently inspected source; actual collector/service behavior remains operator-attested |
| Loopback interpreter on 8788 | Literal `127.0.0.1:8788`, default port 8788, retained supervisor | Literal bind independently verified in source. [Server-owner report 6353866562](https://github.com/3pacs/muse/pull/2#issuecomment-6353866562) also records an `ss -ltnp` loopback listener and service status; that socket/process observation was not independently repeated |
| `stepdadfi.com/gex/feed/all` and `/gex/feed/signals` | Reported actual public feeds `gex.stepdad.finance/feed/all` and `/feed/signals`; original apex/GRID routes preserved | Route/scope report accepted for reconciliation, not certified by reviewer endpoint checks. No new apex routes or URL migration is requested |
| Feeds only; no dashboard in that lane | **User-reported sole serving path: `https://gex.stepdad.finance/dashboard/`**, self-hosted frontend with same-origin feed requests, under the existing site gate | Frontend source/text behavior independently verified. Sole-path selection is the user's reported choice; live serving/gate behavior is operator-attested. Hosted Muse artifact is outside this active serving path |
| No watcher/EOD jobs in the feed-only lane | Already reported watch timer 2 min (watcher/indicator tracker/state alerts), max-pain 5 min, EOD 13:15 PT weekdays; append-only logs; no notifier | MAIN reconciles these reported additions into the expanded self-hosted baseline. No job execution, enable/disable, schedule change or notifier action is directed by this amendment |
| RTD option-chain center plus Nasdaq wings | Reported delayed `cboe_delayed` chain plus optional Nasdaq wings; zero realtime option strikes in the reviewed capture | Source/fixtures preserve delay/provider identity. Runtime chain population/refresh and current market availability are unverified; RTD option-strike merge is outside this closure |
| Legacy quote | RTD collector receipt when supplied, otherwise `public_price` with latency unverified; unknown clocks stay unknown | Corrected schema/source/text controls verified. Quote receipt, provider as-of, build-start time and option-chain time stay distinct |

The original site-root preservation, unrelated port 8787 preservation, no second interpreter against the shared tape, no Muse VM database copy, append-only histories/logs and retained rollback artifacts continue as baseline constraints. Their operational observance remains owner-attested where not independently observed. The presence of the seven expressly reconciled hunks is no longer a “third difference” failure under Amendment 1; this record does not itself trigger any historical rollback command. Unobserved runtime/kill-test/route checks are not silently marked passed.

## Closure and installation classification

The [independent source closure at 1035315a](https://github.com/3pacs/muse/blob/1035315a1051fe7b246262b2284ff09d1082c37a/docs/MUSE-REDTEAM-REVIEW-20261004.md) remains valid: packet manifest **9/9**; owner schema **28/28** reproduced with byte-identical receipt; independent contract **10/10**; normalization/text **12/12**. All four bounded contract/frontend findings and C07 remain closed. This amendment carries those results; no source/model tests were rerun. They establish finite source/contract/text behavior, not trading efficacy, current live options/GEX recovery, actual-browser visual/CSP correctness or deployed byte identity.

[Operator report 6354178550](https://github.com/3pacs/muse/pull/2#issuecomment-6354178550) states the corrected JS hash is installed, gex-watch restarted **2026-10-23 00:10:57 UTC**, `/dashboard/` gives 401 without credentials and 200 with, feeds remain public, and no other file changed. Installation is **OWNER-ATTESTED INSTALLED**. The matching hash reference is consistent with the reviewed JS; independent serving-body/browser identity remains **UNVERIFIED**. MAIN's scope reconciliation is complete despite that separate evidence limit; no new deployment or credentials step is needed to record it.

## Active coordination after this amendment

MAIN's Amendment 2 decision and source/scope reconciliation are **recorded and closed**. Earlier handoff statements awaiting another MAIN owner, takeover, Amendment 2 or a counterproposal are superseded historical status. Do not reopen the original October 20 lane, republish the hosted Muse artifact, move these feeds to the apex, create a replacement frontend author or repeat completed reviews to finish this record.

[Server coordination note 6354225107](https://github.com/3pacs/muse/pull/2#issuecomment-6354225107) confirms the server integration is complete, explicitly rejects duplicate takeover, and identifies this Amendment 2 record as the remaining MAIN item. It adds no new source revision or independent runtime proof. This amendment completes that coordination item; the source-verification closure remains the exact 1035315a/e407fbde evidence cited above.

The existing server/frontend owner retains the already identified narrow serving-response digest/capture and browser-text evidence when available within its existing authority; no fresh operational action is ordered here. Original GEX adapter ownership is unchanged. Offline guarded quote mapping can continue from the pinned contract; completed-OHLCV `update(frame)` remains a different seam. Any genuinely new implementation or runtime evidence returns through the same PR2 handoff. Persistent webhook and current runtime configuration remain untouched.
