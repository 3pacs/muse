# ADOPT-B2 — styled fixture-only browser preview

Response to the ADOPT-B2 assignment staged at docs commit `0bf84e7e`
(PR #2, "docs: accept ADOPT-B1-R1 corrections and stage browser
fixtures"). Everything below is fixture-only: the real dashboard App
mounted in a real browser DOM, driven exclusively by handler responses
generated from the labeled synthetic fixtures. No hosted publish, no
SDK redistribution, no deploy, no live data, no invented scores. All
changes are inside `offline/` (fixture bootstrap / build / style
packaging); no client, server, or pipeline source changed.

## What was built

Four new files under `dashboard-streaming/offline/`:

- `browser-entry.tsx` — the fixture browser bootstrap. Installs the
  case's deterministic receipt clock (frozen `Date`), seeds the
  fixture adapter's responses and the shared QueryClient cache, traps
  `fetch`/XHR (records and refuses any attempt), prepends a
  SYNTHETIC FIXTURE banner naming the case, mounts the real
  `client/src/App` exactly as `client/src/main.tsx` does, then
  measures the rendered DOM and writes a JSON assertion report into
  the page.
- `build-browser.ts` — the browser bundle build (Bun): the fixture
  entry compiled for a browser target with `bun-plugin-tailwind`
  (0.0.15) compiling the production `client/src/theme.css` — the
  same plugin, used the same way (plugin object, not a CLI), as the
  production SDK build (`build.js`: `plugins: [tailwindPlugin]`).
- `browser-fixture.mjs` — the orchestrator. Assembles and attests the
  dependency tree exactly as `offline-build.mjs` does (B1-R1:
  fixture-deps attestation before anything runs), generates the nine
  cases' handler responses by running the real handlers
  (`offline/preview.ts`, independent per-case receipt clocks),
  builds the browser bundle, emits one self-contained page per case,
  and drives Chromium over CDP (`cdp-drive.mjs`) at desktop
  1280×900 and mobile 390×844.
- `cdp-drive.mjs` — a minimal CDP driver (Node, built-in WebSocket).
  Pages load from `file://` URLs; Fetch interception refuses every
  non-file request at the browser level and records it.

## Why CDP and file:// (environment findings, stated openly)

- Chromium's one-shot CLI modes (`--screenshot`, `--dump-dom`,
  `--print-to-pdf`) silently produce no output in this environment
  (verified against a trivial page); the browser itself is healthy
  over CDP (`/json/version` answers, full rendering works), so the
  evidence is driven over CDP.
- A loopback HTTP origin was tried first; Chrome 152's Local Network
  Access checks refuse even the navigation to it here
  (`net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`, zero requests
  reached the server). The pages therefore load from `file://` —
  which also means no IP networking is involved at all. Network
  blocking is asserted at two independent layers: the driver's Fetch
  interception (zero external requests per viewport, recorded in the
  manifest) and the in-page fetch/XHR trap (zero attempts in every
  in-page report).

## Results (headline run, prepared public-only tree)

```
node offline/prepare-deps.mjs --from <production node_modules> \
  --out <public-only tree>     → 57 package dirs, 12 versions attested
node offline/browser-fixture.mjs --deps <public-only tree> \
  --out dashboard-streaming/browser-preview
→ 18/18 case-viewports PASS, exit 0
```

Per case and viewport the in-page report asserts: the case's expected
status and content (LIVE / MARKET CLOSED / FEED DOWN; the
nullable-GEX coverage line "Strike GEX coverage: 3 of 4"; clustering
rendered as true `CLUSTERING (3 in last hour)`, false `isolated`, and
legacy `clustering unknown (legacy row)`; signals-only error keeps
LIVE and shows "Signals unavailable"; future and garbage clocks
render FEED DOWN, never LIVE), zero uncaught errors, zero console
errors, zero outgoing requests, and the synthetic banner present.
Control run against the full production install (real `@hatch`
scope): 18/18 PASS, identical verdicts.

Chart geometry, measured in the real DOM: the App renders exactly
one Recharts chart (net GEX by strike) — 452×224 at desktop,
332×224 at mobile, nonzero and finite in all six data cases; the
error-clock cases render no chart, as expected. (My initial
expectation of two charts was wrong — the level ladder is a custom
div visualization, visible in the screenshots — and was corrected to
the measured reality; the assertion still fails if the one chart
never appears. Separately, the first headline attempt read zero
charts for one case at a fixed 1.2 s measurement under parallel
load; the bootstrap now polls for the chart threshold for up to ~6 s
before asserting. Both corrections are disclosed here rather than
smoothed over.)

Bundle: `app.js` 2,030,433 bytes, `app.css` 24,652 bytes (compiled
from the production `theme.css`). Per the B1 convention the bundles
are hash-recorded in `BROWSER-MANIFEST.json` outputs and not
committed; the committed evidence under
`dashboard-streaming/browser-preview/` is the manifest (browser +
toolchain versions, per-case reports, SHA-256 of inputs / fixtures /
outputs), the nine case pages, the nine handler-response JSONs, the
18 screenshots, and a README.

## Regression state at this pin

- SSR evidence regenerated with `offline-build.mjs`: all 20 retained
  outputs byte-identical to the accepted B1-R1 pin; only
  `preview/BUILD-MANIFEST.json` changed (inputs 27 → 31: the four new
  `offline/` files).
- Backend suites re-run unchanged: boundary tests 51/51;
  `tsc --noEmit` clean (client + server, inside the offline build);
  pipeline compile 12/12; watcher windows 0 failures; J1 replay
  50/50 and 27/27.

## Toolchain (observed)

Chromium 152.0.7977.82 · bun 1.4.2 (package declares bun@1.3.10 —
the same openly-stated drift as B1) · node v24.20.0 · TypeScript
5.6.3 · bun-plugin-tailwind 0.0.15 · fixture adapter
0.0.0-fixture-adapter.

## Retained limits

- `fixture-deps.json` attests direct dependency *versions* only —
  not transitive content, and this is not a clean-machine
  reproducible build (unchanged from B1-R1).
- The browser evidence covers the fixture path only. It does not
  exercise the hosted platform build, the real SDK, or any live
  data path.
- Screenshots and reports were produced by this environment's
  Chromium build; another browser/engine may lay the page out
  differently.
