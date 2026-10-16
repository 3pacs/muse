# ADOPT-B1-R1 — complete the fixture-only portable path

Change note for the ADOPT-B1-R1 assignment (red-team review at docs
`a9463ab5`, PR #2 retitled "docs: review ADOPT-B1 and scope portable
fixture correction"), applied on top of the ADOPT-B1 candidate
`e2cfa0d5` in this same branch
(`implementation/0dte-source-20261015`). Application, ADOPT-F1, and
backend logic are unchanged; every change below is in the offline
build/preview tooling, its dependency evidence, or new synthetic
fixtures. Scope holds from B1 remain: no credentials, no SDK
redistribution, no hosted publish/deployment, no provider collection.

## Correction to the ADOPT-B1 receipts (ours)

The ADOPT-B1 note and PR comment stated that the platform-generated
`server/.generated/privileged.contract` "was used for the typecheck".
That was wrong. The file does not exist in the reference install, no
source imports `@space/privileged` (only the tsconfig path mappings
mention it), the typecheck passes without it, and the committed
BUILD-MANIFEST's `environmentProvided: []` was the truthful record.
The prose overstated the manifest; the manifest stands. The R1 run
again records `environmentProvided: []` — no environment-provided
input is used.

## B1-R1a — adapter assembly no longer depends on a proprietary scope

`offline/offline-build.mjs` previously created the adapter symlink
only while iterating a `@hatch` directory inside `--deps`, so a
public-only tree never received the adapter. Assembly is now
unconditional: every non-`@hatch` package dir is linked, other
`@hatch` children are carried if present, and
`node_modules/@hatch/space-sdk` is ALWAYS linked to the in-package
fixture adapter. Verified by the headline run below: the prepared
tree contains no `@hatch` directory at all and the build resolves
the adapter and completes.

**Public-only dependency preparation.** `offline/fixture-deps.json`
is the fixture-only dependency lock: the 12 direct public
dependencies at the exact versions and registry integrities recorded
in the production `bun.lock` (preserved in-package as provenance),
plus the local adapter as the `@hatch/space-sdk` entry — no
proprietary `file:` tarball appears in the fixture graph.
`offline/prepare-deps.mjs` is the preparation recipe: given an
existing installation it attests every locked version in the source
(mismatch → exit 3, nothing prepared), links all package dirs except
the proprietary `@hatch` scope into the output tree, and writes a
receipt (`<out>.receipt.json`) with the lock hash and observed
versions. Zero network in both preparation and build.

## B1-R1b — adversarial preview matrix

The five baseline cases are retained byte-for-byte in intent. Four
adversarial cases are added, each with machine-checked expectations
(handler payload fields + rendered view-state; a mismatch fails the
build — assertions live in `offline-build.mjs`'s case table and are
enforced by `offline/preview.ts`):

| Case | Fixtures / clock | Asserted outcome |
|---|---|---|
| gex-mix | `feed_all_gex_mix` (new): 2 reported GEX + 1 genuine zero + 1 GEX-absent strike | coverage total 4 / known 3 / missing 1; zero stays `0`, absent stays `null` in the payload; "Strike GEX coverage: 3 of 4" rendered |
| future-clock | `feed_all_future_clock` (new): `updated_at` 2026-01-06 vs **independent receipt clock** 2026-01-05T14:35:35Z | update clock rejected → `getLive.ok=false`, FEED DOWN rendered, "LIVE" absent |
| bad-clock | `feed_all_bad_clock` (new): `updated_at: "not-a-clock"`, fixture-relative path | rejected → FEED DOWN; harness falls back to a finite anchor — no RangeError, evidence written |
| signals-only-error | feed success + `feed_signals_error` | `getLive.ok=true` + LIVE rendered; `getSignals.ok=false` + "Signals unavailable" rendered |

`preview.ts` now accepts an optional independent receipt clock
(argv); without one it keeps the fixture-relative baseline clock,
and an unparseable fixture clock falls back to the default anchor
instead of NaN. Baseline payload JSONs additionally record
`clockSource` (`fixture+30s` / `independent-receipt` /
`fallback-anchor`).

## B1-R1c — dependency receipts with a boundary

The build now runs a **preflight** after assembly and BEFORE any
compiler/bundler child: every fixture-lock entry's version is read
from the assembled tree (adapter included) and compared exactly;
any mismatch or absence exits 3 with the offenders listed and no
build steps run. Negative control, this run: a prepared tree with
`typescript` replaced by version `999.0.0-review-sentinel` is
rejected by name (`locked 5.6.3, observed 999.0.0-review-sentinel`),
exit 3, zero children executed. The manifest now records declared
(`dependenciesExact`, from package.json), locked
(`fixtureLock` path + SHA-256), and observed
(`dependenciesObserved`, read from the tree) versions as three
distinct fields; the Bun manager drift (declared 1.3.10, observed
1.4.2) remains stated.

## Receipts (this run, exact candidate bytes)

Headline run — public-only prepared tree (57 package dirs, no
`@hatch` scope; prep receipt written), `--deps` = that tree:

- preflight: **13 locked dependencies attested** (12 public + adapter)
- boundary tests **51/51**; `tsc --noEmit` clean (client + server)
- server bundle 181,642 B; client `main.js` 2,026,622 B + `main.css`
  78,427 B (regenerable, hash-recorded; not committed)
- **9/9 previews pass their view-state assertions** (5 baseline + 4
  adversarial above)
- BUILD-MANIFEST: 27 inputs / 22 outputs, SHA-256 throughout;
  `environmentProvided: []` (truthful — see correction above)
- Control run against the production install (real `@hatch` scope
  present): identical outcome — adapter substitution and preflight
  behave the same on both trees.
- Backend suites re-run unchanged at this pin: compile 12/12,
  watcher 12/12, J1 50/50, root J1 27/27.

Evidence committed under `dashboard-streaming/preview/` (9 HTML +
9 payload JSON + BUILD-MANIFEST + client shell + README).
