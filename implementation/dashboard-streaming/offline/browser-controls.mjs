// Controlled positive/negative controls for the fixture checker
// (ADOPT-B2-R1). The three checker findings at db14d4bd were reproduced
// by the reviewer with controlled DOM pages running the EXACT clock /
// checker / XHR-hook source extracted from offline/browser-entry.tsx
// (review-browser-checker.mjs, PR #2). This module performs the same
// extraction — identical slice boundaries, identical type-syntax
// erasures — and builds the matching controlled pages so every packet
// run re-proves the corrected behavior alongside the 18 positive cases:
//
//   control-svg        sized wrapper + real SVG + plotted path
//                      -> the checker report must PASS
//   control-empty      sized wrapper, no SVG at all
//                      -> the checker report must FAIL (invalid-chart)
//   control-missing    no wrapper anywhere
//                      -> the checker report must FAIL (budget-expired)
//                         but must still be EMITTED within the budget
//   control-malformed  wrapper + SVG whose only marks are degenerate
//                      (zero-extent path, 0x0 rect)
//                      -> the checker report must FAIL
//   control-xhr        inert sentinel XHR under the exact hook
//                      -> native send never reached, the attempt is
//                         recorded once, and the refusal is labeled
//
// ADOPT-B2-R2 adds the two series-bound negatives the R1 checker still
// passed (axis structure counted as plotted data):
//   control-axis-only       wrapper + SVG with ONLY a cartesian axis
//                           line, zero data shapes -> FAIL (invalid-chart)
//   control-axis-degenerate axis line + data-class shapes that are
//                           both 0x0 -> FAIL (invalid-chart)
// and the intended-negative gate below (classifyControlReport): a
// negative control is a MATCH only when the report is structurally
// complete, belongs to the control's case, fails EXACTLY the chart
// assertion, passes every unrelated assertion, is consistent with its
// pass summary, and settles with the declared outcome. Any other
// failure is a MISMATCH or BLOCKED, never a silent MATCH;
// aggregationCounterexamples() proves the gate against synthetic
// mutated reports on every run.
//
// browser-fixture.mjs drives the pages with offline/cdp-drive.mjs and
// records the reports under "controls" in BROWSER-MANIFEST.json.
import fs from "node:fs";
import path from "node:path";

export function extractSlices(entry) {
  const clock = entry
    .slice(entry.indexOf("const frozenMs ="), entry.indexOf("// --- seed the adapter"))
    .replace("...args: unknown[]", "...args")
    .replace(" as [number]", "")
    .replace("static now(): number", "static now()")
    .replace("(window as { Date: unknown })", "window");
  const checker = entry
    .slice(entry.indexOf("function measureCharts()"))
    .replace("querySelectorAll<HTMLElement>", "querySelectorAll")
    .replace(
      "name: string, pass: boolean, observed?: unknown",
      "name, pass, observed",
    );
  const xhrHook = entry
    .slice(entry.indexOf("const origOpen ="), entry.indexOf("// --- deterministic receipt clock"))
    .replace("this: XMLHttpRequest,", "")
    .replace("_method: string", "_method")
    .replace("url: string | URL", "url")
    .replace(" as never", "")
    .replace(" as typeof XMLHttpRequest.prototype.open", "");
  for (const [name, code] of Object.entries({ clock, checker, xhrHook })) {
    if (!code || code.length < 50) {
      throw new Error("slice extraction failed for " + name);
    }
    if (/<\/script/i.test(code)) {
      throw new Error("slice " + name + " contains a script terminator");
    }
  }
  return { clock, checker, xhrHook };
}

const SETUP =
  "window.packet = { case: \"CONTROL_ID\", frozenIso: \"2026-01-05T14:35:35Z\", " +
  "expect: { minCharts: 1, textIncludes: [\"LIVE\"] } };\n" +
  "window.report = { case: window.packet.case, errors: [], consoleErrors: [], " +
  "requests: [], assertions: [] };\n" +
  "window.__queued = 0;\n" +
  "const nativeSetTimeout = window.setTimeout.bind(window);\n" +
  "window.setTimeout = (fn, delay, ...args) => { window.__queued++; " +
  "return nativeSetTimeout(fn, delay, ...args); };\n";

function checkerPage(id, bodyHtml, slices) {
  return (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n" +
    "<title>CONTROL — " + id + "</title>\n</head>\n<body>\n" +
    "<div id=\"fixture-banner\">SYNTHETIC FIXTURE</div><p>LIVE</p>\n" +
    bodyHtml + "\n" +
    "<script>\n" + SETUP.replace("CONTROL_ID", id) + "</script>\n" +
    "<script>\n" + slices.clock + "\n" + slices.checker + "\n</script>\n" +
    "</body>\n</html>\n"
  );
}

function xhrPage(slices) {
  const attempt =
    "let nativeOpen = 0, nativeSend = 0;\n" +
    "class InertXHR { open() { nativeOpen++; } send() { nativeSend++; } }\n" +
    "window.XMLHttpRequest = InertXHR;\n" +
    "window.report = { requests: [] };\n";
  const verdict =
    "let threw = false;\n" +
    "try { const x = new XMLHttpRequest(); " +
    "x.open(\"GET\", \"https://offline.invalid/control\"); x.send(); } " +
    "catch (e) { threw = true; }\n" +
    "const rep = { case: \"control-xhr\", nativeOpen, nativeSend, " +
    "recordedRequests: window.report.requests, " +
    "refusedSends: window.report.xhrRefused || [], threwOnSend: threw, " +
    "pass: nativeSend === 0 && window.report.requests.length === 1 };\n" +
    "const pre = document.createElement(\"pre\");\n" +
    "pre.id = \"fixture-report\"; pre.style.display = \"none\";\n" +
    "pre.textContent = JSON.stringify(rep);\n" +
    "document.body.appendChild(pre);\n";
  return (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n" +
    "<title>CONTROL — control-xhr</title>\n</head>\n<body>\n" +
    "<div id=\"fixture-banner\">SYNTHETIC FIXTURE</div><p>LIVE</p>\n" +
    "<script>\n" + attempt + "</script>\n" +
    "<script>\n" + slices.xhrHook + "\n</script>\n" +
    "<script>\n" + verdict + "</script>\n" +
    "</body>\n</html>\n"
  );
}

export function buildControls(dir, entryText) {
  const slices = extractSlices(entryText);
  fs.mkdirSync(dir, { recursive: true });
  const sized = "style=\"width:332px;height:224px\"";
  const axisOnly =
    "<g class=\"recharts-cartesian-axis\">" +
    "<line x1=\"10\" y1=\"210\" x2=\"310\" y2=\"210\" stroke=\"black\"/></g>";
  const defs = [
    {
      id: "control-svg", kind: "checker", expectReportPass: true,
      expectedOutcome: "settled",
      html: checkerPage("control-svg",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\"><path d=\"M0 0 L10 10\"/></svg></div>",
        slices),
    },
    {
      id: "control-empty", kind: "checker", expectReportPass: false,
      expectedOutcome: "invalid-chart",
      html: checkerPage("control-empty",
        "<div class=\"recharts-wrapper\" " + sized + "></div>", slices),
    },
    {
      id: "control-missing", kind: "checker", expectReportPass: false,
      expectedOutcome: "budget-expired",
      html: checkerPage("control-missing", "", slices),
    },
    {
      id: "control-malformed", kind: "checker", expectReportPass: false,
      expectedOutcome: "invalid-chart",
      html: checkerPage("control-malformed",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\"><path d=\"M0 0\"/>" +
        "<rect x=\"10\" y=\"10\" width=\"0\" height=\"0\"/></svg></div>",
        slices),
    },
    {
      id: "control-axis-only", kind: "checker", expectReportPass: false,
      expectedOutcome: "invalid-chart",
      html: checkerPage("control-axis-only",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\">" + axisOnly + "</svg></div>",
        slices),
    },
    {
      id: "control-axis-degenerate", kind: "checker", expectReportPass: false,
      expectedOutcome: "invalid-chart",
      html: checkerPage("control-axis-degenerate",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\">" + axisOnly +
        "<g class=\"recharts-bar-rectangles\">" +
        "<path class=\"recharts-rectangle\" d=\"M0 0\"/>" +
        "<rect class=\"recharts-rectangle\" width=\"0\" height=\"0\"/></g>" +
        "</svg></div>",
        slices),
    },
    {
      id: "control-xhr", kind: "xhr", expectReportPass: true,
      expectedOutcome: null,
      html: xhrPage(slices),
    },
  ];
  return defs.map((d) => {
    const page = path.join(dir, d.id + ".html");
    fs.writeFileSync(page, d.html);
    return {
      id: d.id, kind: d.kind, expectReportPass: d.expectReportPass,
      expectedOutcome: d.expectedOutcome, page,
    };
  });
}

// --- ADOPT-B2-R2 intended-negative gate --------------------------------------
// A control report is judged, not merely read for its top-level pass
// boolean. Structure first (a malformed or foreign report is BLOCKED
// and NOT_EVALUABLE, exactly like a missing one), then the intended
// outcome: for an expected-negative checker control the chart
// assertion — and only the chart assertion — must fail, every
// unrelated assertion must pass, the pass summary must agree with the
// assertions, and the settle outcome must be the declared one. An
// expected-negative assertion FAIL classified MATCH stays a control
// result; it never becomes an application PASS.
const CHART_NAME_RE = /^charts mounted with finite SVG plotted geometry \(\d+\/\d+\)$/;
const REQUIRED_ASSERTIONS = [
  "text includes \"LIVE\"",
  "chart",
  "no uncaught errors",
  "no console errors",
  "no outgoing requests",
  "synthetic banner present",
];
const normalizeName = (name) => (CHART_NAME_RE.test(name) ? "chart" : name);

export function classifyControlReport(control, report) {
  const blocked = (reason) => ({
    controlPass: false, classification: "BLOCKED", reason,
    controlExpectation: "NOT_EVALUABLE",
  });
  if (control.kind === "xhr") {
    if (report === null || report === undefined) return blocked("NO_REPORT");
    if (typeof report !== "object" || typeof report.pass !== "boolean") {
      return blocked("INVALID_REPORT");
    }
    const ok =
      report.pass === true &&
      report.nativeSend === 0 &&
      Array.isArray(report.recordedRequests) &&
      report.recordedRequests.length === 1 &&
      Array.isArray(report.refusedSends) &&
      report.refusedSends.length === 1 &&
      report.threwOnSend === true;
    return {
      controlPass: ok,
      classification: report.pass ? "PASS" : "FAIL",
      reason: ok ? "XHR_EVIDENCE_OK" : "XHR_EVIDENCE_MISMATCH",
      controlExpectation: ok ? "MATCH" : "MISMATCH",
    };
  }
  if (report === null || report === undefined) return blocked("NO_REPORT");
  if (
    typeof report !== "object" ||
    typeof report.pass !== "boolean" ||
    !Array.isArray(report.assertions) ||
    report.assertions.some(
      (a) => !a || typeof a.name !== "string" || typeof a.pass !== "boolean",
    ) ||
    !report.settle ||
    typeof report.settle.outcome !== "string"
  ) {
    return blocked("INVALID_REPORT");
  }
  if (report.case !== control.id) return blocked("CASE_MISMATCH");
  const names = report.assertions.map((a) => normalizeName(a.name));
  if (
    names.length !== REQUIRED_ASSERTIONS.length ||
    new Set(names).size !== names.length ||
    !REQUIRED_ASSERTIONS.every((n) => names.includes(n)) ||
    report.pass !== report.assertions.every((a) => a.pass)
  ) {
    return blocked("INVALID_REPORT");
  }
  const failed = report.assertions
    .filter((a) => !a.pass)
    .map((a) => normalizeName(a.name));
  const outcomeOk = report.settle.outcome === control.expectedOutcome;
  const match = control.expectReportPass
    ? report.pass === true && outcomeOk
    : report.pass === false &&
      failed.length === 1 &&
      failed[0] === "chart" &&
      outcomeOk;
  return {
    controlPass: match,
    classification: report.pass ? "PASS" : "FAIL",
    reason: report.pass ? "ASSERTIONS_PASSED" : "ASSERTION_FAILED",
    controlExpectation: match ? "MATCH" : "MISMATCH",
    failedAssertions: failed,
  };
}

// Synthetic aggregation counterexamples: mutated report objects run
// through the same classifier the real reports face. Every mutation
// that the R1 aggregation would have accepted must be rejected here,
// and the two genuine report shapes must MATCH.
export function aggregationCounterexamples() {
  const neg = { id: "control-empty", kind: "checker", expectReportPass: false, expectedOutcome: "invalid-chart" };
  const pos = { id: "control-svg", kind: "checker", expectReportPass: true, expectedOutcome: "settled" };
  const baseNegative = () => ({
    case: "control-empty",
    errors: [], consoleErrors: [], requests: [], xhrRefused: [],
    assertions: [
      { name: "text includes \"LIVE\"", pass: true },
      { name: "charts mounted with finite SVG plotted geometry (0/1)", pass: false, observed: [] },
      { name: "no uncaught errors", pass: true },
      { name: "no console errors", pass: true },
      { name: "no outgoing requests", pass: true },
      { name: "synthetic banner present", pass: true },
    ],
    pass: false,
    viewport: { w: 390, h: 844 },
    charts: [],
    settle: { budgetMs: 6000, elapsedMs: 2414, outcome: "invalid-chart" },
  });
  const basePositive = () => {
    const r = baseNegative();
    r.case = "control-svg";
    r.assertions[1] = { name: "charts mounted with finite SVG plotted geometry (1/1)", pass: true, observed: [] };
    r.pass = true;
    r.settle = { budgetMs: 6000, elapsedMs: 603, outcome: "settled" };
    return r;
  };
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const checks = [];
  const run = (name, control, report, expectPass, expectReason) => {
    const cls = classifyControlReport(control, report);
    const ok =
      cls.controlPass === expectPass &&
      (expectReason === undefined || cls.reason === expectReason);
    checks.push({
      name, pass: ok,
      classification: cls.classification, reason: cls.reason,
      controlExpectation: cls.controlExpectation,
    });
  };
  run("genuine intended-negative report matches", neg, baseNegative(), true);
  run("genuine positive report matches", pos, basePositive(), true);
  run("unrelated error only cannot satisfy a negative", neg, (() => {
    const r = baseNegative();
    r.assertions[1].pass = true;
    r.assertions[2].pass = false;
    r.errors = ["synthetic unrelated error"];
    return r;
  })(), false);
  run("intended chart failure plus unrelated error cannot satisfy a negative", neg, (() => {
    const r = baseNegative();
    r.assertions[2].pass = false;
    r.errors = ["synthetic unrelated error"];
    return r;
  })(), false);
  run("inconsistent pass summary is blocked", neg, (() => {
    const r = baseNegative();
    r.assertions.forEach((a) => { a.pass = true; });
    return r;
  })(), false, "INVALID_REPORT");
  run("missing assertions are blocked", neg, (() => {
    const r = baseNegative();
    delete r.assertions;
    return r;
  })(), false, "INVALID_REPORT");
  run("duplicate assertions are blocked", neg, (() => {
    const r = baseNegative();
    r.assertions.push(clone(r.assertions[0]));
    return r;
  })(), false, "INVALID_REPORT");
  run("wrong-case report is blocked", neg, (() => {
    const r = baseNegative();
    r.case = "synthetic-other-case";
    return r;
  })(), false, "CASE_MISMATCH");
  run("wrong settle outcome cannot satisfy a negative", neg, (() => {
    const r = baseNegative();
    r.settle.outcome = "settled";
    return r;
  })(), false);
  run("minimal malformed report is blocked", neg, { pass: false }, false, "INVALID_REPORT");
  run("missing report stays blocked/unevaluated", neg, null, false, "NO_REPORT");
  run("unexpectedly passing negative cannot satisfy its control", neg, (() => {
    const r = baseNegative();
    r.assertions.forEach((a) => { a.pass = true; });
    r.pass = true;
    return r;
  })(), false);
  run("positive control with failing chart cannot match", pos, (() => {
    const r = basePositive();
    r.assertions[1].pass = false;
    r.pass = false;
    r.settle.outcome = "invalid-chart";
    return r;
  })(), false);
  run("missing settle block is blocked", neg, (() => {
    const r = baseNegative();
    delete r.settle;
    return r;
  })(), false, "INVALID_REPORT");
  return {
    checks,
    passed: checks.filter((c) => c.pass).length,
    failed: checks.filter((c) => !c.pass).length,
  };
}
