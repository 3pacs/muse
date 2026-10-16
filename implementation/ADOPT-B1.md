# ADOPT-B1 — dependency-locked offline build and fixture preview

Change note for the ADOPT-B1 assignment (PR #2 comment 6204507725,
2026-10-15), applied on top of the ADOPT-F1 candidate
`e8274a1e93db780746e88a6938445abb1e14e880` in this same lane
(`implementation/0dte-source-20261015`). Scope honored: no credentials,
no SDK redistribution, no hosted publish, no deployment, no provider
data collection. The proprietary `@hatch/space-sdk` tarball is NOT in
this package — only a fixture-only adapter written against its public
type surface (below).

## Toolchain and dependency lock

`dashboard-streaming/` now carries the project's own **`bun.lock`**
(text lockfile, lockfileVersion 2, 84 integrity-hashed packages,
SHA-256 `a577073250445bc115750db617ec76338db4b0409304d456ff3194e31d6b6937`)
and **`bunfig.toml`** (hoisted linker, per-space install cache) — the
dependency lock the intake package was missing.

| Tool | Declared | Used in this run |
|---|---|---|
| bun | `packageManager: bun@1.3.10` | 1.4.2 (host binary) |
| node | — | v24.20.0 |
| typescript | 5.6.3 (devDependency, exact) | 5.6.3 |

Direct dependencies are exact-pinned in `package.json` (no ranges):
react 19.2.5, react-dom 19.2.5, @tanstack/react-query 5.100.10,
drizzle-orm 0.45.2, recharts 2.15.3, zod 4.4.3,
@hatch/space-sdk via `file:` tarball (platform-proprietary, withheld);
dev: @types/bun 1.4.2, @types/react 19.2.14, @types/react-dom 19.2.3,
tailwindcss 4.1.13, tailwindcss-safe-area 1.3.0, typescript 5.6.3.
Declared-vs-observed drift is stated, not hidden: the run used the
host's bun 1.4.2 against a lockfile written for the declared manager.

## Portable entrypoint

```
node implementation/dashboard-streaming/offline/offline-build.mjs \
  --deps <node_modules installed from bun.lock> --out <dir>
```

Zero downloads; a missing `--deps` is a hard error. The entrypoint:
copies the dashboard tree to a throwaway work dir; assembles
node_modules from `--deps`, substituting ONLY `@hatch/space-sdk` with
the fixture adapter; runs the ADOPT-F1 boundary tests (51) and both
TypeScript project checks; builds the server bundle (`bun build`) and
the client bundle (adapter `buildClient`); renders the fixture
previews; and writes `BUILD-MANIFEST.json` mapping every source input
to every output by SHA-256, with toolchain versions and fixture
hashes recorded.

## Fixture-only platform adapter

`dashboard-streaming/offline/adapter/` — a small stand-in package
named `@hatch/space-sdk` (version `0.0.0-fixture-adapter`), written
against the SDK's public type surface so the production sources
compile and run unchanged:

- `index.ts` (server): `z` re-exported from public zod; `defineAction`
  is the identity over the same spec shape (handlers stay invocable);
  `Ctx.db` typed as a schema-generic drizzle LibSQL accessor.
- `client.ts`: `createActionClient` returns the harness-seeded fixture
  responses instead of POSTing; `spaceQueryClient` is a plain
  QueryClient; `SafeAreaTopScrim` renders nothing (cosmetic).
- `build.ts`: plain `Bun.build` of the client entrypoint.

Deliberate differences from the platform, stated plainly: no runtime
request/response schema validation by the adapter; Tailwind utilities
are NOT compiled (the SDK's Tailwind plugin owns that in production);
asset naming is Bun's default; previews are SSR (charts render as
empty frames). None of these touch data semantics.

## Fixture preview

`dashboard-streaming/offline/preview.ts` stubs `fetch` with the
labeled synthetic fixtures, freezes the clock at each fixture's own
`updated_at` +30s, invokes the REAL server handlers against an
in-memory drizzle-shaped fake DB, seeds the exact responses into a
QueryClient, and server-renders the REAL App. Five cases (evidence in
`dashboard-streaming/preview/`, incl. per-case payload JSON):

| Case | Fixtures | Rendered view-state |
|---|---|---|
| success | feed_all_success + feed_signals_success | LIVE; print with cluster=false → "isolated" |
| last-session | feed_all_last_session + signals success | MARKET CLOSED |
| legacy | feed_all_success + feed_signals_legacy_tags | LIVE; prints → "clustering unknown (legacy row)" |
| clustering | feed_all_success + feed_signals_cluster_true (new supplemental fixture) | LIVE; "⚠️ CLUSTERING (3 in last hour)" |
| error | feed_all_error + feed_signals_error | FEED DOWN; signals panel unavailable |

## Receipts (this run, exact candidate bytes)

- `offline-build.mjs` end-to-end: boundary tests **51/51**; `tsc
  --noEmit` clean on client and server projects (against the
  adapter-typed SDK surface); server bundle 181,642 bytes; client
  bundle `main.js` 2,026,622 bytes + `main.css` 78,427 bytes; five
  previews rendered; `BUILD-MANIFEST.json`: 25 source inputs, 14
  outputs, all SHA-256 recorded (committed under
  `dashboard-streaming/preview/`; the bulky bundles themselves are
  regenerable and hash-recorded rather than committed).
- One environment-provided file was used for the typecheck only: the
  platform-generated `server/.generated/privileged.contract` from the
  reference install (recorded in the manifest as environment-provided;
  it is generated by the platform on every real build and is not
  candidate source).
- Backend suites re-run unchanged at this pin: 12 pipeline modules
  compile; watcher **12/12**; J1 replay **50/50**; `build_signals()`
  synthetic checks identical to the accepted intake pin.
