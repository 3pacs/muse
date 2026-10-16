// CDP driver for the fixture browser evidence (ADOPT-B2).
//
//   node offline/cdp-drive.mjs <jobs.json>
//
// jobs.json: {
//   "chrome": "/path/to/chrome",
//   "resultPath": "/abs/results.json",
//   "jobs": [{ "id": "success-desktop", "page": "/abs/success.html",
//              "w": 1280, "h": 900, "mobile": false,
//              "shotPath": "/abs/shots/success-desktop.png" }]
// }
//
// The fixture pages are loaded from file:// URLs — no HTTP server and
// no IP networking are involved at all. For each job: opens a fresh
// target, blocks every request that is not file:/data:/blob: (Fetch
// interception — the browser itself refuses it), navigates to the
// page, waits for the page's own assertion report
// (<pre id="fixture-report">, written by offline/browser-entry.tsx),
// captures a PNG screenshot, and records the report plus every
// blocked/external request it saw. Results are written to resultPath
// as JSON. Exit 0 when every job produced a report and a screenshot;
// the CALLER judges pass/fail from the reports.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const jobsFile = process.argv[2];
if (!jobsFile) {
  console.error("usage: cdp-drive.mjs <jobs.json>");
  process.exit(2);
}
const cfg = JSON.parse(fs.readFileSync(jobsFile, "utf8"));

// --- launch Chromium ----------------------------------------------------------
const profile = fs.mkdtempSync("/tmp/cdp-profile-");
const chrome = spawn(cfg.chrome, [
  "--headless=new", "--no-sandbox", "--disable-gpu",
  "--disable-dev-shm-usage", "--hide-scrollbars",
  // file:// pages may load their own module scripts/styles; any
  // non-file request is still refused by the Fetch interception below.
  "--allow-file-access-from-files",
  "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
  "--user-data-dir=" + profile, "--no-first-run", "about:blank",
], { stdio: "ignore" });
const portFile = path.join(profile, "DevToolsActivePort");
let wsPath = null;
for (let i = 0; i < 100 && !wsPath; i++) {
  if (fs.existsSync(portFile)) {
    const lines = fs.readFileSync(portFile, "utf8").trim().split("\n");
    if (lines.length >= 2) wsPath = lines[1];
  }
  if (!wsPath) await new Promise((r) => setTimeout(r, 100));
}
if (!wsPath) {
  console.error("chromium did not publish DevToolsActivePort");
  process.exit(2);
}
const port = fs.readFileSync(portFile, "utf8").trim().split("\n")[0];

// --- minimal CDP client ---------------------------------------------------------
const ws = new WebSocket("ws://127.0.0.1:" + port + wsPath);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = rej;
});
let nextId = 1;
const pending = new Map();
const listeners = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) rej(new Error(msg.error.message));
    else res(msg.result);
  } else if (msg.method) {
    for (const fn of listeners) fn(msg);
  }
};
function send(method, params = {}, sessionId) {
  const id = nextId++;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  ws.send(JSON.stringify(payload));
  return new Promise((res, rej) => pending.set(id, { res, rej }));
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- run the jobs -----------------------------------------------------------------
const results = [];
for (const job of cfg.jobs) {
  const external = [];
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const onEvent = (msg) => {
    if (msg.sessionId !== sessionId) return;
    if (msg.method === "Fetch.requestPaused") {
      const url = msg.params.request.url;
      if (url.startsWith("file://") || url.startsWith("data:") || url.startsWith("blob:") || url === "about:blank") {
        send("Fetch.continueRequest", { requestId: msg.params.requestId }, sessionId).catch(() => {});
      } else {
        external.push(url);
        send("Fetch.failRequest", { requestId: msg.params.requestId, errorReason: "BlockedByClient" }, sessionId).catch(() => {});
      }
    }
  };
  listeners.push(onEvent);
  try {
    await send("Page.enable", {}, sessionId);
    await send("Runtime.enable", {}, sessionId);
    await send("Fetch.enable", { patterns: [{ urlPattern: "*" }] }, sessionId);
    await send("Emulation.setDeviceMetricsOverride", {
      width: job.w, height: job.h, deviceScaleFactor: 1, mobile: !!job.mobile,
    }, sessionId);
    await send("Page.navigate", { url: "file://" + job.page }, sessionId);
    let report = null;
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline && !report) {
      const r = await send("Runtime.evaluate", {
        expression: "document.getElementById('fixture-report')?.textContent ?? null",
        returnByValue: true,
      }, sessionId).catch(() => null);
      const v = r?.result?.value;
      if (typeof v === "string" && v.length > 2) {
        try {
          report = JSON.parse(v);
        } catch {
          report = null;
        }
      }
      if (!report) await sleep(250);
    }
    let shotBytes = 0;
    if (report) {
      const shot = await send("Page.captureScreenshot", { format: "png" }, sessionId);
      const buf = Buffer.from(shot.data, "base64");
      fs.mkdirSync(path.dirname(job.shotPath), { recursive: true });
      fs.writeFileSync(job.shotPath, buf);
      shotBytes = buf.length;
    }
    results.push({ id: job.id, report, screenshotBytes: shotBytes, externalRequests: external });
    console.log(job.id + ": " + (report ? "report captured (" + shotBytes + "B png)" : "NO REPORT"));
  } finally {
    listeners.splice(listeners.indexOf(onEvent), 1);
    await send("Target.closeTarget", { targetId }).catch(() => {});
  }
}
fs.writeFileSync(cfg.resultPath, JSON.stringify({ results }, null, 2) + "\n");
ws.close();
chrome.kill("SIGKILL");
fs.rmSync(profile, { recursive: true, force: true });
const missing = results.filter((r) => !r.report || r.screenshotBytes === 0);
process.exit(missing.length ? 4 : 0);
