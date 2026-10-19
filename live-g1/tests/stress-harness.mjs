// STRESS-P1 harness: drives the ACTUAL public controller (LIVE_G1.refresh())
// of the built LIVE-G1 delivery page in headless Chrome via CDP, with the
// transport stubbed at window.fetch (the page's only transport seam).
// Same method class as the reviewer's controller workloads: real page, real
// refresh(), scripted per-route responses, DOM + global state assertions.
//
//   node stress-harness.mjs <built.html> <results.json>
//
// Exit 0 when every case passes.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const htmlPath = path.resolve(process.argv[2]);
const outPath = path.resolve(process.argv[3]);
const CHROME = "/opt/meta-chromium/chrome";

// --- launch Chromium ---------------------------------------------------------
const profile = fs.mkdtempSync("/tmp/stress-profile-");
const chrome = spawn(CHROME, [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
  "--hide-scrollbars", "--allow-file-access-from-files",
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
if (!wsPath) { console.error("chromium did not publish DevToolsActivePort"); process.exit(2); }
const port = fs.readFileSync(portFile, "utf8").trim().split("\n")[0];

// --- minimal CDP client -------------------------------------------------------
const ws = new WebSocket("ws://127.0.0.1:" + port + wsPath);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let nextId = 1;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) rej(new Error(msg.error.message)); else res(msg.result);
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

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Fetch.enable", { patterns: [{ urlPattern: "*" }] }, sessionId);
ws.addEventListener("message", (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.method === "Fetch.requestPaused" && msg.sessionId === sessionId) {
    const url = msg.params.request.url;
    if (url.startsWith("file://") || url.startsWith("data:") || url === "about:blank") {
      send("Fetch.continueRequest", { requestId: msg.params.requestId }, sessionId).catch(() => {});
    } else {
      send("Fetch.failRequest", { requestId: msg.params.requestId, errorReason: "BlockedByClient" }, sessionId).catch(() => {});
    }
  }
});
await send("Page.navigate", { url: "file://" + htmlPath }, sessionId);
await sleep(600);

async function evl(expression) {
  const r = await send("Runtime.evaluate", {
    expression, awaitPromise: true, returnByValue: true,
  }, sessionId);
  if (r.exceptionDetails) {
    throw new Error("page evaluate failed: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  }
  return r.result.value;
}

// --- install transport stub + fixture builders --------------------------------
await evl(`
window.__fetchLog = [];
window.__plan = {};
window.fetch = async (url) => {
  const u = String(url);
  window.__fetchLog.push(u);
  const key = Object.keys(window.__plan).find(k => u.endsWith(k));
  const step = key ? window.__plan[key] : null;
  if (!step) throw new TypeError('no plan for ' + u);
  if (step.delay) await new Promise(r => setTimeout(r, step.delay));
  if (step.throw) throw new TypeError(step.throw);
  return {
    ok: step.status === undefined ? true : step.status < 400,
    status: step.status === undefined ? 200 : step.status,
    json: async () => {
      if (step.badJson) throw new SyntaxError('Unexpected token < in JSON');
      return JSON.parse(JSON.stringify(step.body));
    },
  };
};
LIVE_G1.transport.base = 'http://adapter.test/adapter/v1';
const F = (v, ts) => ({ value: v, unit: 'USD', source: 'stress-fixture', source_at: ts, received_at: ts, stale: false, unavailable: false });
window.__status = (ts, o = {}) => ({
  adapter_version: o.av !== undefined ? o.av : 'live-g1/v1',
  backend_pin: o.pin !== undefined ? o.pin : '8649ad54',
  backend: { interpreter: { reachable: o.reachable !== false } },
  data_vintage: { latest_record_at: ts, stale: !!o.stale, stale_reason: o.stale ? 'fixture stale' : null },
});
window.__snap = (ts, spot, o = {}) => {
  const s = {
    adapter_version: o.av !== undefined ? o.av : 'live-g1/v1',
    backend_pin: o.pin !== undefined ? o.pin : '8649ad54',
    recorded_at: ts,
    fields: { spot: F(spot, ts), max_pain: F(768, ts), gamma_flip: F(769.5, ts), pin_score: F(40, ts), call_wall: F(775, ts), put_wall: F(773, ts) },
  };
  if (o.fields !== undefined) s.fields = o.fields;
  return s;
};
window.__hist = (ts, spot, o = {}) => {
  const n = o.n || 3;
  const h = {
    adapter_version: o.av !== undefined ? o.av : 'live-g1/v1',
    backend_pin: o.pin !== undefined ? o.pin : '8649ad54',
    count: n,
    records: Array.from({ length: n }, () => ({ recorded_at: ts, spot, max_pain: 768, gamma_flip: 769.5, pin_score: 40 })),
  };
  if (o.records !== undefined) h.records = o.records;
  return h;
};
window.__tuple = (ts, spot, o = {}) => ({
  '/status': { body: window.__status(ts, o.status || {}) },
  '/snapshot': { body: window.__snap(ts, spot, o.snap || {}) },
  '/history?limit=20': { body: window.__hist(ts, spot, o.hist || {}) },
});
window.__state = () => {
  const v = document.querySelector('#metrics .card .v');
  const rows = document.querySelectorAll('#ranges tbody tr');
  return {
    spot: v ? v.textContent.trim() : null,
    rowCount: rows.length,
    conn: document.getElementById('conn-badge').textContent,
    fresh: document.getElementById('fresh-badge').textContent,
    alertShown: document.getElementById('alert').style.display === 'block',
    note: document.getElementById('refresh-note').textContent,
    snapTs: (window.__SNAPSHOT__ && window.__SNAPSHOT__.recorded_at) || null,
    histLen: window.__HISTORY__ && Array.isArray(window.__HISTORY__.records) ? window.__HISTORY__.records.length : 'non-array:' + typeof (window.__HISTORY__ && window.__HISTORY__.records),
    histSpot: window.__HISTORY__ && Array.isArray(window.__HISTORY__.records) && window.__HISTORY__.records[0] ? window.__HISTORY__.records[0].spot : null,
    lastError: LIVE_G1.lastError,
    failed: !!LIVE_G1._transportFailed,
    zoneDateOnly: LIVE_G1._hasExplicitZone('2026-10-07'),
    frameDateOnly: LIVE_G1._frameTs({ recorded_at: '2026-10-07' }),
  };
};
window.__refresh = async () => {
  let rej = null;
  try { await LIVE_G1.refresh(); } catch (e) { rej = String(e && e.message || e); }
  return Object.assign(window.__state(), { rej });
};
window.__setPlan = (plan) => { window.__plan = plan; window.__fetchLog = []; };
'ok'`);

// --- cases ---------------------------------------------------------------------
const results = [];
function record(id, pass, observed) {
  results.push({ id, pass: !!pass, observed });
  console.log((pass ? "PASS " : "FAIL ") + id + (pass ? "" : " :: " + JSON.stringify(observed)));
}
const T0 = "2026-10-06T07:00:00Z", T2 = "2026-10-06T07:11:00Z", T3 = "2026-10-06T07:15:00Z",
      T4 = "2026-10-06T07:20:00Z", T5 = "2026-10-06T07:23:00Z", T6 = "2026-10-06T07:26:00Z",
      T8 = "2026-10-06T07:40:00Z", T9 = "2026-10-06T07:45:00Z", T10 = "2026-10-06T07:50:00Z";
const plan = (expr) => evl(`window.__setPlan(${expr}); 'set'`);

// boot: embedded data renders
let s = await evl(`window.__state()`);
record("boot_embedded", s.spot === "774.94" && s.snapTs === "2026-10-06T05:46:01.101928+00:00", s);

// admit a valid base frame @T0 spot 800
await plan(`window.__tuple('${T0}', 800)`);
s = await evl(`window.__refresh()`);
record("admit_base", s.rej === null && s.spot === "800.00" && s.snapTs === T0 && s.conn === "connected" && s.fresh === "fresh" && s.histSpot === 800, s);

// C07: newer snapshot, history.records is an object -> whole tuple rejected, no throw
await plan(`window.__tuple('${T2}', 900, { hist: { records: { bogus: 1 } } })`);
s = await evl(`window.__refresh()`);
record("c07_malformed_history_rejected_atomically",
  s.rej === null && s.spot === "800.00" && s.snapTs === T0 && s.histSpot === 800 && s.histLen === 3, s);

// C07: valid retry at the SAME timestamp must be admitted (identity not consumed)
await plan(`window.__tuple('${T2}', 900)`);
s = await evl(`window.__refresh()`);
record("c07_valid_retry_same_frame_admitted", s.rej === null && s.spot === "900.00" && s.snapTs === T2 && s.histSpot === 900, s);

// C08: fields as a string -> rejected, tuple intact
await plan(`window.__tuple('${T3}', 950, { snap: { fields: 'not-a-map' } })`);
s = await evl(`window.__refresh()`);
record("c08_string_fields_rejected", s.rej === null && s.spot === "900.00" && s.snapTs === T2, s);

// C08: fields as an array -> rejected, tuple intact
await plan(`window.__tuple('${T3}', 950, { snap: { fields: [1, 2, 3] } })`);
s = await evl(`window.__refresh()`);
record("c08_array_fields_rejected", s.rej === null && s.spot === "900.00" && s.snapTs === T2, s);

// C08: valid retry at same timestamp admitted
await plan(`window.__tuple('${T3}', 950)`);
s = await evl(`window.__refresh()`);
record("c08_valid_retry_admitted", s.rej === null && s.spot === "950.00" && s.snapTs === T3, s);

// C09 variants @T4: each must leave the T3 tuple intact
const c09 = [
  ["c09_snapshot_adapter_version", `window.__tuple('${T4}', 960, { snap: { av: 'unsupported/v99' } })`],
  ["c09_history_adapter_version", `window.__tuple('${T4}', 960, { hist: { av: 'unsupported/v99' } })`],
  ["c09_foreign_backend_pin", `window.__tuple('${T4}', 960, { snap: { pin: 'foreign-backend' } })`],
  ["c09_mixed_status_version", `window.__tuple('${T4}', 960, { status: { av: 'live-g1/v2' } })`],
];
for (const [id, expr] of c09) {
  await plan(expr);
  s = await evl(`window.__refresh()`);
  record(id, s.rej === null && s.spot === "950.00" && s.snapTs === T3, s);
}
// C09: valid retry at same timestamp admitted
await plan(`window.__tuple('${T4}', 960)`);
s = await evl(`window.__refresh()`);
record("c09_valid_retry_admitted", s.rej === null && s.spot === "960.00" && s.snapTs === T4, s);

// C10: reachable=false + stale=false must not display fresh (tuple itself admissible)
await plan(`window.__tuple('${T5}', 970, { status: { reachable: false, stale: false } })`);
s = await evl(`window.__refresh()`);
record("c10_contradictory_status_not_fresh",
  s.rej === null && s.spot === "970.00" && s.conn === "disconnected" && s.fresh !== "fresh", s);

// C06 control: transport failure retains last-good + failure state
await plan(`({ '/status': { throw: 'boom' }, '/snapshot': { throw: 'boom' }, '/history?limit=20': { throw: 'boom' } })`);
s = await evl(`window.__refresh()`);
record("c06_transport_failure_retains", s.spot === "970.00" && s.snapTs === T5 && s.failed === true && !!s.lastError && s.alertShown === true, s);

// C06 control: equal frame does not clear failure state
await plan(`window.__tuple('${T5}', 970)`);
s = await evl(`window.__refresh()`);
record("c06_equal_frame_keeps_failure", s.spot === "970.00" && s.failed === true, s);

// C06 control: genuinely newer valid frame recovers
await plan(`window.__tuple('${T6}', 980)`);
s = await evl(`window.__refresh()`);
record("c06_newer_recovers", s.rej === null && s.spot === "980.00" && s.failed === false && s.lastError === null && s.fresh === "fresh", s);

// C11/R4 clocks: timezone-less and date-only rejected; offsets honored
await plan(`window.__tuple('2026-10-06T07:30:00', 990)`);
s = await evl(`window.__refresh()`);
record("c11_timezone_less_rejected", s.rej === null && s.spot === "980.00" && s.snapTs === T6, s);
await plan(`window.__tuple('2026-10-07', 990)`);
s = await evl(`window.__refresh()`);
record("r4_date_only_rejected", s.rej === null && s.spot === "980.00" && s.snapTs === T6 && s.zoneDateOnly === false && s.frameDateOnly === null, s);
await plan(`window.__tuple('2026-10-06T12:56:00+05:30', 990)`); // == T6 instant
s = await evl(`window.__refresh()`);
record("c11_equal_instant_offset_not_newer", s.rej === null && s.spot === "980.00" && s.snapTs === T6, s);
await plan(`window.__tuple('2026-10-06T12:57:00+05:30', 990)`); // == 07:27Z, newer
s = await evl(`window.__refresh()`);
record("c11_newer_offset_admitted", s.rej === null && s.spot === "990.00", s);

// burst coalescing: 10 concurrent refreshes, 40ms routes -> exactly 2 snapshot fetches
await plan(`(() => { const p = window.__tuple('${T8}', 995); for (const k of Object.keys(p)) p[k].delay = 40; return p; })()`);
s = await evl(`(async () => {
  const ps = [];
  for (let i = 0; i < 10; i++) ps.push(LIVE_G1.refresh());
  await Promise.all(ps);
  await new Promise(r => setTimeout(r, 300));
  const st = window.__state();
  st.snapFetches = window.__fetchLog.filter(u => u.includes('/snapshot')).length;
  return st;
})()`);
record("burst_coalesces_to_one_followup", s.spot === "995.00" && s.snapFetches === 2, s);

// C12: 20,000 history records admitted, 12 visible rows, all retained
await plan(`window.__tuple('${T9}', 996, { hist: { n: 20000 } })`);
s = await evl(`window.__refresh()`);
record("c12_large_history", s.rej === null && s.spot === "996.00" && s.histLen === 20000 && s.rowCount === 12, s);

// malformed JSON positive control: parse failure is a transport failure, tuple retained
await plan(`({ '/status': { body: window.__status('${T10}') }, '/snapshot': { badJson: true }, '/history?limit=20': { body: window.__hist('${T10}', 999) } })`);
s = await evl(`window.__refresh()`);
record("badjson_retains_tuple", s.spot === "996.00" && s.failed === true && !!s.lastError, s);

// final recovery
await plan(`window.__tuple('${T10}', 999)`);
s = await evl(`window.__refresh()`);
record("final_recovery", s.rej === null && s.spot === "999.00" && s.failed === false && s.lastError === null, s);

const failed = results.filter((r) => !r.pass);
fs.writeFileSync(outPath, JSON.stringify({ total: results.length, passed: results.length - failed.length, failed: failed.map((f) => f.id), results }, null, 2) + "\n");
console.log(`\n${results.length - failed.length}/${results.length} pass`);
await send("Target.closeTarget", { targetId }).catch(() => {});
ws.close();
chrome.kill("SIGKILL");
fs.rmSync(profile, { recursive: true, force: true });
process.exit(failed.length ? 1 : 0);
