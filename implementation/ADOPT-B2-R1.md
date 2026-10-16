# ADOPT-B2-R1 — bounded browser failure evidence

Response to the ADOPT-B2-R1 assignment staged at docs commit
`899b80bd` (PR #2, "docs: verify B2 browser packet and scope checker
failure evidence"). The three reproduced findings were all in the
fixture harness (`offline/browser-entry.tsx`), none in the App. Every
change is inside `dashboard-streaming/offline/` plus this lane's
evidence and documents; no App/client, server, F1, or pipeline source
changed, and the 18 positive case-viewports remain correct.

## Erratum (B2 wording, corrected here, not rewritten there)

ADOPT-B2.md described the in-page layer as trapping fetch/XHR and
refusing attempts at "two independent layers". That was true for
fetch and for the CDP layer, but the in-page XHR hook only *observed*:
it recorded the URL and delegated to the native `open`, and `send`
was not hooked at all. The reviewer's inert-sentinel probe (native
open ×1, native send ×1, recorded ×1) was correct. R1c below makes
the in-page refusal claim true; ADOPT-B2.md's historical text is
left as written, and this note is the correction of record.

## The three fixes (all in `offline/browser-entry.tsx`)

**R1a — settle budget on a monotonic clock.** The settle loop no
longer compares against `Date.now()` (frozen at the fixture instant,
so the old deadline could never pass). It measures elapsed time with
`performance.now()` against the declared 6000 ms budget. A chart
that never mounts now produces an explicit failed assertion report
within the budget; the driver's separate ~30 s NO REPORT path is
unchanged and stays distinguishable from an evaluated assertion
failure. Every report now records
`settle: {budgetMs, elapsedMs, outcome}` with outcome one of
`settled`, `invalid-chart`, or `budget-expired`. The App's receipt /
data clock remains frozen — only the wait is monotonic.

**R1b — chart validation inspects the SVG and its plotted marks.**
`measureCharts()` now reports, per `.recharts-wrapper`: wrapper
size, whether an `svg` is present, the SVG's rendered size, the
number of plotted marks (`path, rect, circle, line, polyline,
polygon`) and how many have finite geometry with positive extent on
at least one axis. A wrapper counts only when it is sized, contains
a sized SVG, and has at least one such mark. A sized empty wrapper
therefore fails, and so does an SVG whose marks are all degenerate.
Zero/null semantics are preserved: a genuine zero-valued bar has a
finite bounding box with positive width, so it still counts — no
positive-height requirement was introduced. The expected chart
count is unchanged (1 for data cases, 0 for error cases). The
assertion was renamed accordingly: "charts mounted with finite SVG
plotted geometry (valid/total)". A wrapper that exists but stays
invalid for a sustained 1800 ms grace period fails fast
(`invalid-chart`) instead of waiting out the budget; no wrapper at
all waits the full budget (`budget-expired`).

**R1c — XHR refused in-page.** The hook now overrides both methods
and delegates to neither: `open()` records the attempt in
`report.requests` and remembers the URL on the instance;
`send()` appends a labeled refusal to the report's separate
`xhrRefused` list (`"send refused in-page (fixture network block):
<url>"`) and throws. The native open/send are never invoked. Fetch
refusal and the CDP Fetch interception are unchanged. Expected
negative-test attempts stay in the record, labeled, in
`xhrRefused` — they are not silently removed, and they do not touch
`report.requests`, so a sent XHR still fails the "no outgoing
requests" assertion exactly as before.

## Controlled pages (new file `offline/browser-controls.mjs`)

The packet run now also drives five controlled pages through the
same CDP driver, using source slices extracted from
`browser-entry.tsx` with the reviewer's own slice boundaries and
type-syntax erasures (`review-browser-checker.mjs`, PR #2). Results
are recorded under `controls` in `BROWSER-MANIFEST.json`:

| control | page | required | observed (headline run) |
|---|---|---|---|
| control-svg | 332×224 wrapper + SVG + plotted path | report pass=true | pass=true, settled 603 ms |
| control-empty | 332×224 wrapper, no SVG | report pass=false | pass=false, invalid-chart at 2,414 ms |
| control-missing | no wrapper | failure report emitted within budget | pass=false, budget-expired at 6,011 ms |
| control-malformed | SVG with only degenerate marks (zero-extent path, 0×0 rect) | report pass=false | pass=false, invalid-chart at 2,408 ms |
| control-xhr | inert sentinel XHR under the exact hook | native send never reached, attempt recorded | nativeOpen=0, nativeSend=0, recorded ×1, refusal labeled in `xhrRefused` |

## Item 4 — mobile gex-mix chart capture

The current 18 screenshots are retained byte-for-byte. One capture
was added from the same real App fixture path:
`browser-preview/shots/gex-mix-mobile-chart.png` — the mobile
(390×844) gex-mix page shot full-height via
`Page.captureScreenshot` with `captureBeyondViewport`, 390×2701, so
the "Strike GEX coverage: 3 of 4" label and the chart plot are
visible in one frame. Recorded under `extraCaptures` in
`BROWSER-MANIFEST.json`. Evidence capture only; no dashboard change.

## Results

Headline run (prepared public-only dependency tree, Chromium
152.0.7977.82, Bun 1.4.2, Node v24.20.0, TypeScript 5.6.3):

- 18/18 case-viewports PASS. Data cases measure one valid chart at
  452×224 (desktop) / 332×224 (mobile) with 7–9 valid plotted marks;
  error cases measure none. Zero errors, zero console errors, zero
  outgoing requests, zero external requests at the CDP layer.
  Positive settle outcomes are `settled` at ~0.6 s.
- Controls 5/5 as tabled above.
- Control run against the production install (real `@hatch` scope):
  18/18 PASS, controls 5/5, full-height capture produced —
  identical verdicts.
- Browser bundle: app.js 2,032,363 B, app.css 24,652 B (hashes in
  `BROWSER-MANIFEST.json`; the bundles themselves remain
  hash-recorded, not committed — the B1/B2 convention).
- SSR preview regenerated with `offline-build.mjs`: preflight
  13/13 attested, boundary tests 51/51, tsc clean; all retained SSR
  outputs byte-identical to the ADOPT-B2 pin (only BUILD-MANIFEST
  inputs changed: the three edited offline sources plus the new
  `offline/browser-controls.mjs`, 31 → 32).
- Backend suites re-run unchanged: py_compile 12/12 OK, watcher
  0 failures, J1 50/50, older J1 27/27.

The disclosed ADOPT-B2 timing flake and its correction history are
preserved as recorded in ADOPT-B2.md / TESTS.md; nothing about it
is relabeled here. Screenshot byte variance across runs was
observed again in this run's data-case captures, which is why the
committed 18 PNGs are the retained B2 originals, paired in the
manifest with this run's fresh reports.
