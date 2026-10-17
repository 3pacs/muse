# ADOPT-B2-R2 — series-bound chart validation and intended-negative gate

Bounded completion of the two findings left open at the ADOPT-B2-R1
acceptance (docs head `69554fb1`, PR #2), implemented on top of the
accepted B2-R1 pin `7addef72`. Scope is limited to the fixture
checker and its control aggregation — `offline/browser-entry.tsx`
(`measureCharts` + the settle gate), `offline/browser-controls.mjs`
(control definitions, the report classifier, synthetic
counterexamples), and `offline/browser-fixture.mjs` (fixture binding,
gate-judged controls, manifest). No App/client, server, F1, or
pipeline source changed; expected chart counts and the 18 positive
scenario meanings are unchanged.

## R2a — axes count as plotted data no longer

`measureCharts` now classifies every SVG shape before counting it:

- **Decorations** (never data): any shape inside `<defs>`, or with an
  ancestor (or itself) carrying an axis/grid/legend/tooltip/reference
  class (`cartesian-axis`, `cartesian-grid`, `recharts-legend`,
  `recharts-tooltip`, `recharts-reference`, `xAxis`, `yAxis`).
- **Series marks**: every remaining shape. A series mark is *valid*
  only with finite geometry and positive extent on **both** axes.
- **Binding**: when a chart is expected, the settle gate additionally
  requires the total valid-series count to reach
  `expect.minSeriesMarks`, which `browser-fixture.mjs` computes per
  case from the case fixture's nonzero `gamma.by_strike` rows
  (2 for every data case here: strikes 500 → 210.4, 505 → 320.1).
  A genuine zero row's bar may be collapsed or absent; it counts as
  a series mark but is never required to have pixels.

Observed on the real App cases (both runs): each data chart now
measures **10 marks = 8 decorations + 2 series marks, 2 valid** —
exactly the fixture's two nonzero rows; under R1 the same charts
reported 7–9 "valid marks" because grid/axis shapes counted.

New controlled negatives (the reviewer's two real-Chrome witnesses,
now first-class controls in `browser-controls.mjs`):

| Control | Content | Result |
|---|---|---|
| control-axis-only | sized SVG, only a cartesian axis line | chart FAIL, `invalid-chart`, 2,409 ms (marks 1 = 1 decoration, 0 series) |
| control-axis-degenerate | axis line + two data-class shapes, both 0×0 | chart FAIL, `invalid-chart`, 2,414 ms (series candidates 2, valid 0) |

Both previously returned PASS/settled (~603 ms) under the R1 checker.
The five accepted R1 controls keep their outcomes: sized-SVG control
settles (603 ms); empty wrapper `invalid-chart` (2,422 ms); missing
chart emits its report at `budget-expired` (6,013 ms); malformed
geometry `invalid-chart` (2,408 ms); XHR sentinel refused with
native send never reached. The control-svg template is byte-stable,
so harnesses that mutate it (e.g. replacing
`<path d="M0 0 L10 10"/>`) keep working, and the chart assertion's
name format is unchanged.

## R2b — any failure can no longer certify a negative control

The R1 aggregation accepted a negative control whenever the
report's top-level `pass` equalled the expectation, so
`{pass:false}` alone, or a report whose chart passed but an
unrelated assertion failed, counted as a correct negative.
`classifyControlReport` (in `browser-controls.mjs`) now judges
every control report:

1. **Structure**: non-object reports, non-boolean `pass`, missing /
   malformed assertions, or a missing settle outcome are
   `BLOCKED / INVALID_REPORT` — unevaluated, and they fail the run.
   A missing report stays `BLOCKED / NO_REPORT` (preserved from R1:
   absence is never converted into an assertion failure).
2. **Case**: `report.case` must equal the control id
   (`CASE_MISMATCH` otherwise).
3. **Completeness/consistency**: the assertion names must be
   exactly the required six (chart assertion normalized by its
   `(n/m)` suffix), unique, and `report.pass` must equal the
   conjunction of the assertions.
4. **Intended outcome**: a positive control MATCHes only on a
   passing report with the declared settle outcome; a negative
   control MATCHes only when **exactly the chart assertion fails**,
   every unrelated assertion passes, and the settle outcome is the
   declared one (`invalid-chart` / `budget-expired`). An
   expected-negative assertion FAIL classified MATCH remains a
   control result — it is never relabeled an application PASS.
5. **XHR**: judged on sentinel evidence, not the pass boolean —
   native send count 0, exactly one recorded attempt, exactly one
   labeled refusal, send threw.

Every manifest control entry now records `classification`,
`reason`, and `controlExpectation` alongside its report.
`aggregationCounterexamples()` runs 14 synthetic mutated reports
through the same classifier on every packet run (genuine negative +
positive MATCH; unrelated-error-only, chart+unrelated, inconsistent
summary, missing assertions, duplicate assertions, wrong case,
wrong settle outcome, minimal `{pass:false}`, missing report,
unexpectedly-passing negative, chart-failing positive, missing
settle — all rejected with the classifications above): **14/14**
behave as intended, recorded under `aggregationProof` in
BROWSER-MANIFEST.json.

## Runs at this candidate

- Headline (prepared public-only tree; Bun 1.4.2, Node v24.20.0,
  TypeScript 5.6.3, Chromium 152.0.7977.82): **18/18**
  case-viewports PASS; controls **7/7 MATCH**; aggregation proof
  14/14; bundle app.js 2,033,436 B (sha256 e05f50afb7d9…),
  app.css 24,652 B — hash-recorded in BROWSER-MANIFEST.json, not
  committed, per the standing convention.
- Production-install control run: 18/18, controls 7/7, identical
  verdicts.
- SSR preview regenerated: preflight 13/13, boundary tests 51/51,
  tsc clean; **all 19 retained SSR outputs byte-identical** to the
  B2-R1 pin (BUILD-MANIFEST inputs refreshed — only the three
  offline files above changed hash; outputs untouched).
- Backend suites unchanged: py_compile 12/12, watcher 0 failures,
  J1 50/50, root J1 27/27.

## Provenance

The 18 B2 screenshots and the R1 full-height mobile capture are
retained byte-for-byte (this run's re-renders differed in bytes on
some cases, as in R1); BROWSER-MANIFEST.json pairs the retained
PNGs with the fresh R2 reports and their screenshot hashes record
the retained files. Case pages changed bytes because the inlined
packet now carries `expect.minSeriesMarks`; handler responses are
byte-identical to R1.
