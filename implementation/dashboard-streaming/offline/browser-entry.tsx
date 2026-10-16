// Fixture-only BROWSER bootstrap (ADOPT-B2).
//
// This is the entrypoint of the fixture browser bundle. It mounts the
// REAL dashboard App in a real browser DOM, driven only by the handler
// responses inlined into the generated page as `window.__FIXTURE__`
// (those responses are produced by the real server handlers running on
// the labeled synthetic fixtures — see browser-fixture.mjs, which reuses
// preview.ts). Before mounting it:
//   - installs the case's deterministic receipt clock (a frozen Date),
//   - seeds the fixture adapter's responses + the shared QueryClient,
//   - records every console error, uncaught error, and outgoing request
//     attempt (fetch/XHR are trapped and refused: the fixture path must
//     make NO network requests),
//   - prepends an explicit SYNTHETIC FIXTURE banner naming the case.
// After mount it measures the rendered DOM (status text, chart geometry)
// and writes a machine-checkable report into <pre id="fixture-report">.
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { spaceQueryClient } from "@hatch/space-sdk/client";
import { App } from "../client/src/App";
import "../client/src/theme.css";

type FixturePacket = {
  case: string;
  frozenIso: string;
  clockSource: string;
  getLive: unknown;
  getSignals: unknown;
  expect: {
    textIncludes?: string[];
    textExcludes?: string[];
    minCharts?: number;
  };
};

const packet = (window as { __FIXTURE__?: FixturePacket }).__FIXTURE__;
if (!packet) throw new Error("fixture packet missing (window.__FIXTURE__)");

// --- observation traps (installed before the App loads) ---------------------
const report = {
  case: packet.case,
  errors: [] as string[],
  consoleErrors: [] as string[],
  requests: [] as string[],
  xhrRefused: [] as string[],
  assertions: [] as { name: string; pass: boolean; observed?: unknown }[],
};
(window as { __REPORT__?: unknown }).__REPORT__ = report;
window.addEventListener("error", (e) => {
  report.errors.push(String(e.message ?? e.error ?? "unknown error"));
});
window.addEventListener("unhandledrejection", (e) => {
  report.errors.push("unhandledrejection: " + String(e.reason));
});
const origError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  report.consoleErrors.push(args.map(String).join(" ").slice(0, 300));
  origError(...args);
};
const recordRequest = (url: string) => {
  report.requests.push(url);
  return Promise.reject(new Error("fixture browser: network blocked: " + url));
};
window.fetch = ((input: unknown) =>
  recordRequest(String((input as { url?: string })?.url ?? input))) as typeof fetch;
const origOpen = XMLHttpRequest.prototype.open;
const origSend = XMLHttpRequest.prototype.send;
void origOpen;
void origSend;
// ADOPT-B2-R1: XHR is REFUSED in-page, not merely observed. open()
// records the attempt and remembers the URL on the instance, but the
// native open is never invoked; send() records a labeled refusal and
// throws, so the native send is never reached either. (The natives are
// captured above only so the trap's installation is explicit; the void
// references document that non-delegation is deliberate.) The CDP Fetch
// interception in the driver remains the second, outer layer.
const xhrUrls = new WeakMap();
XMLHttpRequest.prototype.open = function (
  this: XMLHttpRequest,
  _method: string,
  url: string | URL,
) {
  report.requests.push(String(url));
  xhrUrls.set(this, String(url));
  return undefined;
} as typeof XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.send = function () {
  const url = String(xhrUrls.get(this) || "(unopened)");
  const refused = report.xhrRefused || (report.xhrRefused = []);
  refused.push("send refused in-page (fixture network block): " + url);
  throw new Error("fixture browser: network blocked (XHR refused): " + url);
};

// --- deterministic receipt clock -------------------------------------------
const frozenMs = Date.parse(packet.frozenIso);
const RealDate = Date;
class FrozenDate extends RealDate {
  constructor(...args: unknown[]) {
    super(...((args.length ? args : [frozenMs]) as [number]));
  }
  static now(): number {
    return frozenMs;
  }
}
(window as { Date: unknown }).Date = FrozenDate;

// --- seed the adapter + query cache -----------------------------------------
(globalThis as { __FIXTURE_RESPONSES__?: unknown }).__FIXTURE_RESPONSES__ = {
  getLive: packet.getLive,
  getSignals: packet.getSignals,
};
spaceQueryClient.setQueryData(["live-feed"], packet.getLive);
spaceQueryClient.setQueryData(["signals-feed"], packet.getSignals);

// --- synthetic banner ---------------------------------------------------------
const banner = document.createElement("div");
banner.id = "fixture-banner";
banner.textContent =
  "SYNTHETIC FIXTURE — case \"" + packet.case + "\" — NOT MARKET DATA — " +
  "clock frozen at " + packet.frozenIso + " (" + packet.clockSource + ")";
banner.setAttribute(
  "style",
  "background:#7a1f1f;color:#fff;padding:10px 14px;font:13px monospace;",
);
document.body.prepend(banner);
document.title = "SYNTHETIC FIXTURE — " + packet.case;

// --- mount the real App (same shape as client/src/main.tsx) ------------------
const rootEl = document.querySelector<HTMLElement>("[data-generated-space-root]");
if (!rootEl) throw new Error("missing generated space root element");
createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={spaceQueryClient}>
      <div className="hatch-space-root" data-hatch-space-root>
        <App />
      </div>
    </QueryClientProvider>
  </StrictMode>,
);

// --- measure + assert once the App has settled ------------------------------
// ADOPT-B2-R1: the settle budget runs on a MONOTONIC elapsed clock
// (performance.now), never on the frozen fixture Date — a chart that
// never mounts now produces an explicit failed assertion report within
// the budget instead of looping forever against a deadline that cannot
// move. (The App's receipt/data clock stays frozen; only the wait is
// monotonic.) Chart validity inspects the rendered SVG and its plotted
// marks, not just the wrapper box: a sized but empty wrapper does not
// count, and neither does a wrapper whose marks are all degenerate
// (zero-extent or non-finite). A genuine zero-valued bar still counts:
// its mark's bounding box is finite with positive extent on one axis.
// A wrapper that exists but stays invalid for a sustained grace period
// fails fast with outcome "invalid-chart"; no wrapper at all waits out
// the full budget ("budget-expired"); a valid chart settles at once.
function measureCharts() {
  return Array.from(
    document.querySelectorAll<HTMLElement>(".recharts-wrapper"),
  ).map((el) => {
    const r = el.getBoundingClientRect();
    const svg = el.querySelector("svg");
    let svgW = 0;
    let svgH = 0;
    let marks = 0;
    let validMarks = 0;
    if (svg) {
      const sr = svg.getBoundingClientRect();
      svgW = sr.width;
      svgH = sr.height;
      const markEls = svg.querySelectorAll(
        "path, rect, circle, line, polyline, polygon",
      );
      marks = markEls.length;
      markEls.forEach((m) => {
        const b = m.getBoundingClientRect();
        if (
          Number.isFinite(b.width) &&
          Number.isFinite(b.height) &&
          (b.width > 0 || b.height > 0)
        ) {
          validMarks++;
        }
      });
    }
    const valid =
      Number.isFinite(r.width) &&
      Number.isFinite(r.height) &&
      r.width > 0 &&
      r.height > 0 &&
      svg !== null &&
      Number.isFinite(svgW) &&
      Number.isFinite(svgH) &&
      svgW > 0 &&
      svgH > 0 &&
      validMarks > 0;
    return {
      w: Math.round(r.width),
      h: Math.round(r.height),
      svg: svg !== null,
      svgW: Math.round(svgW),
      svgH: Math.round(svgH),
      marks,
      validMarks,
      valid,
    };
  });
}
function check(name: string, pass: boolean, observed?: unknown) {
  report.assertions.push({ name, pass, observed });
}
const settleBudgetMs = 6000;
const settleStartMs = performance.now();
const settleDeadlineMs = settleStartMs + settleBudgetMs;
const invalidGraceMs = 1800;
let invalidSinceMs = -1;
function settle() {
  const minCharts = packet.expect.minCharts ?? 0;
  const nowMs = performance.now();
  const charts = measureCharts();
  const validCount = charts.filter((c) => c.valid).length;
  let outcome = null;
  if (validCount >= minCharts) {
    outcome = "settled";
  } else if (charts.length > 0) {
    if (invalidSinceMs < 0) invalidSinceMs = nowMs;
    if (nowMs - invalidSinceMs >= invalidGraceMs) outcome = "invalid-chart";
  } else {
    invalidSinceMs = -1;
  }
  if (outcome === null && nowMs >= settleDeadlineMs) outcome = "budget-expired";
  if (outcome === null) {
    setTimeout(settle, 200);
    return;
  }
  const visibleText = document.body.innerText.replace(/\s+/g, " ");
  for (const s of packet.expect.textIncludes ?? []) {
    check("text includes " + JSON.stringify(s), visibleText.includes(s));
  }
  for (const s of packet.expect.textExcludes ?? []) {
    check("text excludes " + JSON.stringify(s), !visibleText.includes(s));
  }
  check(
    "charts mounted with finite SVG plotted geometry (" +
      validCount +
      "/" +
      charts.length +
      ")",
    validCount >= minCharts,
    charts,
  );
  check("no uncaught errors", report.errors.length === 0, report.errors);
  check("no console errors", report.consoleErrors.length === 0, report.consoleErrors);
  check("no outgoing requests", report.requests.length === 0, report.requests);
  check(
    "synthetic banner present",
    document.getElementById("fixture-banner") !== null,
  );
  const pre = document.createElement("pre");
  pre.id = "fixture-report";
  pre.style.display = "none";
  pre.textContent = JSON.stringify({
    ...report,
    pass: report.assertions.every((a) => a.pass),
    viewport: { w: window.innerWidth, h: window.innerHeight },
    charts,
    settle: {
      budgetMs: settleBudgetMs,
      elapsedMs: Math.round(performance.now() - settleStartMs),
      outcome,
    },
  });
  document.body.appendChild(pre);
}
setTimeout(settle, 600);
