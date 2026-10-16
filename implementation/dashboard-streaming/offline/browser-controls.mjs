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
  const defs = [
    {
      id: "control-svg", kind: "checker", expectReportPass: true,
      html: checkerPage("control-svg",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\"><path d=\"M0 0 L10 10\"/></svg></div>",
        slices),
    },
    {
      id: "control-empty", kind: "checker", expectReportPass: false,
      html: checkerPage("control-empty",
        "<div class=\"recharts-wrapper\" " + sized + "></div>", slices),
    },
    {
      id: "control-missing", kind: "checker", expectReportPass: false,
      html: checkerPage("control-missing", "", slices),
    },
    {
      id: "control-malformed", kind: "checker", expectReportPass: false,
      html: checkerPage("control-malformed",
        "<div class=\"recharts-wrapper\" " + sized + ">" +
        "<svg width=\"332\" height=\"224\"><path d=\"M0 0\"/>" +
        "<rect x=\"10\" y=\"10\" width=\"0\" height=\"0\"/></svg></div>",
        slices),
    },
    {
      id: "control-xhr", kind: "xhr", expectReportPass: true,
      html: xhrPage(slices),
    },
  ];
  return defs.map((d) => {
    const page = path.join(dir, d.id + ".html");
    fs.writeFileSync(page, d.html);
    return { id: d.id, kind: d.kind, expectReportPass: d.expectReportPass, page };
  });
}
