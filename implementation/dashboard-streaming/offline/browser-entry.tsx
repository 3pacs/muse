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
XMLHttpRequest.prototype.open = function (
  this: XMLHttpRequest,
  _method: string,
  url: string | URL,
) {
  report.requests.push(String(url));
  return origOpen.apply(this, arguments as never);
} as typeof XMLHttpRequest.prototype.open;

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

// --- measure + assert after the App settles -----------------------------------
// --- measure + assert once the App has settled ------------------------------
// Recharts' ResponsiveContainer only renders its wrapper after measuring
// a positive parent size, which can lag under load; poll for the chart
// threshold for up to ~6s instead of assuming a fixed delay suffices.
// If the threshold never arrives the assertion fails for real.
function measureCharts() {
  return Array.from(
    document.querySelectorAll<HTMLElement>(".recharts-wrapper"),
  ).map((el) => {
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  });
}
function check(name: string, pass: boolean, observed?: unknown) {
  report.assertions.push({ name, pass, observed });
}
const settleDeadline = Date.now() + 6000;
function settle() {
  const minCharts = packet.expect.minCharts ?? 0;
  const sized = measureCharts().filter(
    (c) => c.w > 0 && c.h > 0 && Number.isFinite(c.w) && Number.isFinite(c.h),
  );
  if (sized.length < minCharts && Date.now() < settleDeadline) {
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
  const charts = measureCharts();
  check(
    "charts mounted with nonzero finite geometry (" +
      sized.length + "/" + charts.length + ")",
    sized.length >= minCharts,
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
  });
  document.body.appendChild(pre);
}
setTimeout(settle, 600);
