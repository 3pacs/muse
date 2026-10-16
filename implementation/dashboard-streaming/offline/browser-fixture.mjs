#!/usr/bin/env node
// Fixture-only BROWSER evidence builder (ADOPT-B2).
//
// Mounts the REAL dashboard App in a real browser DOM (Chromium), driven
// only by handler responses generated from the labeled synthetic
// fixtures, and records screenshots + machine-checkable DOM assertions
// for all nine cases at desktop and narrow-mobile viewports.
//
//   node offline/browser-fixture.mjs --deps <prepared-or-full node_modules>
//                                   --out <dir>
//                                   [--work <dir>] [--fixtures <dir>]
//                                   [--chrome <path>] [--keep-work]
//
// Steps (no step downloads anything):
//   1. Assemble an isolated work copy of this space (sources only),
//      overlay the dependency tree onto it, and attest every direct
//      dependency version against offline/fixture-deps.json BEFORE
//      anything runs (mismatch -> exit 3, nothing built).
//   2. Generate the nine cases' handler responses by running the real
//      server handlers on the synthetic fixtures (offline/preview.ts),
//      each against its own INDEPENDENT receipt clock.
//   3. Build the browser bundle from the real client sources with the
//      production Tailwind plugin (offline/build-browser.ts).
//   4. For each case, emit a self-contained page that inlines the case's
//      responses as the fixture packet (window.__FIXTURE__), and load it
//      in headless Chromium at 1280x900 and 390x844. The page freezes
//      its clock at the case's receipt instant, traps and refuses any
//      outgoing request, renders a SYNTHETIC FIXTURE banner, mounts the
//      App, then measures the DOM and writes a JSON assertion report
//      into the page (read back here via --dump-dom). Screenshots are
//      captured per case per viewport.
//   5. Write BROWSER-MANIFEST.json: browser + toolchain versions, the
//      per-case reports, and SHA-256 hashes of inputs, fixtures used,
//      and outputs.
//
// Exit codes: 0 all cases pass · 2 usage/assembly error · 3 dependency
// attestation failure · 4 a case failed its assertions.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const spaceRoot = path.resolve(here, "..");

function arg(name, fallback) {
  const i = process.argv.indexOf("--" + name);
  return i >= 0 ? process.argv[i + 1] : fallback;
}
const depsDir = arg("deps");
const outDir = arg("out");
const keepWork = process.argv.includes("--keep-work");
const fixturesDir = path.resolve(
  arg("fixtures", path.join(spaceRoot, "../fixtures")),
);
const chromePath = arg("chrome", "/opt/meta-chromium/chrome");
if (!depsDir || !outDir) {
  console.error(
    "usage: browser-fixture.mjs --deps <node_modules> --out <dir> [--work <dir>] [--fixtures <dir>] [--chrome <path>]",
  );
  process.exit(2);
}
const workDir = path.resolve(
  arg("work", fs.mkdtempSync(path.join("/tmp/", "browser-fixture-"))),
);
const outAbs = path.resolve(outDir);

// The nine synthetic cases: exactly the fixtures, receipt clocks, and
// expectations of the SSR evidence (offline-build.mjs), with the
// expectations translated to browser-visible text. A "" receipt means
// preview.ts's own independent default receipt clock is used.
// Error clocks must render FEED DOWN, never LIVE.
// minCharts is 1 for data cases: the App renders exactly one Recharts
// chart (net GEX by strike, measured 452x224 desktop / 332x224 mobile
// in the rehearsal); the level ladder is a custom div visualization.
const CASES = [
  { name: "success", fixtures: ["feed_all_success.json", "feed_signals_success.json"], receipt: "",
    expect: { textIncludes: ["LIVE", "isolated"], textExcludes: ["FEED DOWN", "MARKET CLOSED", "CLUSTERING (", "clustering unknown"], minCharts: 1 } },
  { name: "last-session", fixtures: ["feed_all_last_session.json", "feed_signals_success.json"], receipt: "",
    expect: { textIncludes: ["MARKET CLOSED"], textExcludes: ["FEED DOWN"], minCharts: 1 } },
  { name: "legacy", fixtures: ["feed_all_success.json", "feed_signals_legacy_tags.json"], receipt: "",
    expect: { textIncludes: ["clustering unknown (legacy row)"], textExcludes: ["CLUSTERING (", "isolated"], minCharts: 1 } },
  { name: "clustering", fixtures: ["feed_all_success.json", "feed_signals_cluster_true.json"], receipt: "",
    expect: { textIncludes: ["CLUSTERING (3 in last hour)"], textExcludes: ["isolated", "FEED DOWN"], minCharts: 1 } },
  { name: "error", fixtures: ["feed_all_error.json", "feed_signals_error.json"], receipt: "",
    expect: { textIncludes: ["FEED DOWN"], textExcludes: [], minCharts: 0 } },
  { name: "gex-mix", fixtures: ["feed_all_gex_mix.json", "feed_signals_success.json"], receipt: "",
    expect: { textIncludes: ["Strike GEX coverage: 3 of 4"], textExcludes: ["FEED DOWN"], minCharts: 1 } },
  { name: "future-clock", fixtures: ["feed_all_future_clock.json", "feed_signals_success.json"], receipt: "2026-01-05T14:35:35+00:00",
    expect: { textIncludes: ["FEED DOWN"], textExcludes: ["LIVE", "MARKET CLOSED"], minCharts: 0 } },
  { name: "bad-clock", fixtures: ["feed_all_bad_clock.json", "feed_signals_success.json"], receipt: "",
    expect: { textIncludes: ["FEED DOWN"], textExcludes: ["LIVE", "MARKET CLOSED"], minCharts: 0 } },
  { name: "signals-only-error", fixtures: ["feed_all_success.json", "feed_signals_error.json"], receipt: "",
    expect: { textIncludes: ["LIVE", "Signals unavailable"], textExcludes: ["FEED DOWN"], minCharts: 1 } },
];
const VIEWPORTS = [
  { name: "desktop", w: 1280, h: 900, mobile: false },
  { name: "mobile", w: 390, h: 844, mobile: true },
];

// Same assembly/attestation discipline as offline-build.mjs (B1-R1).
const PINNED = JSON.parse(
  fs.readFileSync(path.join(here, "fixture-deps.json"), "utf8"),
).dependencies;
const EXCLUDES = new Set(["node_modules", "dist", "preview", "browser-preview"]);

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}
function listFiles(root, base = root, acc = []) {
  for (const e of fs.readdirSync(root, { withFileTypes: true })) {
    if (base === root && EXCLUDES.has(e.name)) continue;
    const p = path.join(root, e.name);
    if (e.isDirectory()) listFiles(p, base, acc);
    else if (e.isFile()) acc.push(path.relative(base, p));
  }
  return acc.sort();
}
function copyDir(src, dst, top = false) {
  fs.mkdirSync(dst, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    if (top && EXCLUDES.has(e.name)) continue;
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else if (e.isFile()) fs.copyFileSync(s, d);
  }
}
function installedVersion(pkgDir) {
  const pj = path.join(pkgDir, "package.json");
  if (!fs.existsSync(pj)) return null;
  try {
    return JSON.parse(fs.readFileSync(pj, "utf8")).version ?? null;
  } catch {
    return null;
  }
}
function attestTree(nmRoot, label) {
  const bad = [];
  for (const [name, entry] of Object.entries(PINNED)) {
    const got = installedVersion(path.join(nmRoot, ...name.split("/")));
    if (got !== entry.version) {
      bad.push(label + ": " + name + " want " + entry.version + " got " + got);
    }
  }
  return bad;
}
function assemble() {
  const srcBad = attestTree(path.resolve(depsDir), "deps-source");
  if (srcBad.length) {
    console.error("ATTESTATION FAILURE (source tree):\n" + srcBad.join("\n"));
    process.exit(3);
  }
  fs.rmSync(workDir, { recursive: true, force: true });
  copyDir(spaceRoot, workDir, true);
  const nmDst = path.join(workDir, "node_modules");
  fs.mkdirSync(nmDst, { recursive: true });
  const depsAbs = path.resolve(depsDir);
  for (const e of fs.readdirSync(depsAbs, { withFileTypes: true })) {
    if (e.name === "@hatch") continue;
    fs.symlinkSync(path.join(depsAbs, e.name), path.join(nmDst, e.name), "dir");
  }
  // The fixture adapter occupies the SDK's module specifier
  // UNCONDITIONALLY (identical assembly for full and public-only
  // trees): any other @hatch packages in the source tree are linked
  // through, and @hatch/space-sdk is the adapter directory itself.
  const hatchDir = path.join(nmDst, "@hatch");
  fs.mkdirSync(hatchDir, { recursive: true });
  const depsHatch = path.join(depsAbs, "@hatch");
  if (fs.existsSync(depsHatch)) {
    for (const child of fs.readdirSync(depsHatch)) {
      if (child === "space-sdk") continue;
      fs.symlinkSync(path.join(depsHatch, child), path.join(hatchDir, child), "dir");
    }
  }
  fs.symlinkSync(
    path.join(workDir, "offline", "adapter"),
    path.join(hatchDir, "space-sdk"),
    "dir",
  );
  const treeBad = attestTree(nmDst, "assembled-tree");
  if (treeBad.length) {
    console.error("ATTESTATION FAILURE (assembled tree):\n" + treeBad.join("\n"));
    process.exit(3);
  }
  return {
    adapterVersion: installedVersion(path.join(hatchDir, "space-sdk")),
  };
}
function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: "utf8", ...opts });
  if (r.status !== 0) {
    console.error("FAILED: " + cmd + " " + args.join(" "));
    console.error((r.stdout ?? "").slice(-3000));
    console.error((r.stderr ?? "").slice(-3000));
    process.exit(2);
  }
  return r.stdout ?? "";
}

// --- assemble + attest -------------------------------------------------------
const { adapterVersion } = assemble();
console.log("assembled work copy at " + workDir + " (deps attested)");

// --- handler responses for the nine cases (offline/preview.ts) --------------
const respDir = path.join(workDir, ".responses");
for (const c of CASES) {
  // preview.ts usage: <case> <feed_all.json> <signals.json> <outDir> [receiptIso]
  const args = ["run", "offline/preview.ts", c.name,
    path.join(fixturesDir, c.fixtures[0]), path.join(fixturesDir, c.fixtures[1]),
    respDir];
  if (c.receipt) args.push(c.receipt);
  run("bun", args, { cwd: workDir, timeout: 180_000 });
}
console.log("handler responses generated for " + CASES.length + " cases");

// --- browser bundle ------------------------------------------------------------
const bundleDir = path.join(workDir, ".browser-out");
run("bun", ["run", "offline/build-browser.ts"], {
  cwd: workDir,
  timeout: 300_000,
  env: { ...process.env, OFFLINE_BROWSER_OUT: bundleDir },
});
const bundleFiles = fs.readdirSync(bundleDir);
const jsName = bundleFiles.find((f) => f.endsWith(".js"));
const cssName = bundleFiles.find((f) => f.endsWith(".css"));
if (!jsName || !cssName) {
  console.error("browser bundle missing js/css outputs: " + bundleFiles.join(", "));
  process.exit(2);
}
fs.mkdirSync(path.join(outAbs, "assets"), { recursive: true });
fs.copyFileSync(path.join(bundleDir, jsName), path.join(outAbs, "assets", "app.js"));
fs.copyFileSync(path.join(bundleDir, cssName), path.join(outAbs, "assets", "app.css"));
fs.mkdirSync(path.join(outAbs, "responses"), { recursive: true });
console.log("browser bundle built: " + jsName + " + " + cssName);

// --- per-case pages ---------------------------------------------------------------
for (const c of CASES) {
  const payload = JSON.parse(
    fs.readFileSync(path.join(respDir, c.name + ".payload.json"), "utf8"),
  );
  fs.copyFileSync(
    path.join(respDir, c.name + ".payload.json"),
    path.join(outAbs, "responses", c.name + ".json"),
  );
  const packet = {
    case: c.name,
    frozenIso: payload.frozenClock,
    clockSource: payload.clockSource,
    getLive: payload.getLive,
    getSignals: payload.getSignals,
    expect: c.expect,
  };
  const inline = JSON.stringify(packet).replace(/</g, "\\u003c");
  const html =
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n" +
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n" +
    "<title>SYNTHETIC FIXTURE — " + c.name + "</title>\n" +
    "<link rel=\"stylesheet\" href=\"./assets/app.css\" />\n" +
    "<script>window.__FIXTURE__ = " + inline + ";</script>\n</head>\n<body>\n" +
    "<div data-generated-space-root></div>\n" +
    "<script type=\"module\" src=\"./assets/app.js\"></script>\n</body>\n</html>\n";
  fs.writeFileSync(path.join(outAbs, c.name + ".html"), html);
}
console.log("case pages written");

// --- Chromium runs (CDP-driven; the one-shot CLI modes do not render in
// this environment, the browser itself is healthy over CDP) ----------------
const chromeVersion = run(chromePath, ["--version"]).trim();
fs.mkdirSync(path.join(outAbs, "shots"), { recursive: true });
const jobs = [];
for (const c of CASES) {
  for (const vp of VIEWPORTS) {
    jobs.push({
      id: c.name + "-" + vp.name,
      page: path.join(outAbs, c.name + ".html"),
      w: vp.w, h: vp.h, mobile: vp.mobile,
      shotPath: path.join(outAbs, "shots", c.name + "-" + vp.name + ".png"),
    });
  }
}
const jobsPath = path.join(workDir, ".cdp-jobs.json");
const resultsPath = path.join(workDir, ".cdp-results.json");
fs.writeFileSync(jobsPath, JSON.stringify({
  chrome: chromePath, resultPath: resultsPath, jobs,
}, null, 2));
{
  const r = spawnSync("node", [path.join(workDir, "offline", "cdp-drive.mjs"), jobsPath],
    { encoding: "utf8", timeout: 600_000 });
  process.stdout.write(r.stdout ?? "");
  if (r.status !== 0 && r.status !== 4) {
    console.error((r.stderr ?? "").slice(-3000));
    console.error("CDP driver failed with status " + r.status);
    process.exit(2);
  }
}
const drive = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
const byId = new Map(drive.results.map((r) => [r.id, r]));
const caseResults = [];
let anyFail = false;
for (const c of CASES) {
  const viewports = [];
  for (const vp of VIEWPORTS) {
    const res = byId.get(c.name + "-" + vp.name);
    const report = res?.report ?? null;
    const shotPath = path.join(outAbs, "shots", c.name + "-" + vp.name + ".png");
    const shotBytes = fs.existsSync(shotPath) ? fs.readFileSync(shotPath) : null;
    const external = res?.externalRequests ?? ["<driver result missing>"];
    const pass = !!report && report.pass === true && !!shotBytes &&
      shotBytes.length > 5000 && external.length === 0;
    if (!pass) anyFail = true;
    viewports.push({
      viewport: vp.name,
      size: vp.w + "x" + vp.h,
      screenshot: "shots/" + c.name + "-" + vp.name + ".png",
      screenshotBytes: shotBytes ? shotBytes.length : 0,
      screenshotSha256: shotBytes ? sha256(shotBytes) : null,
      externalRequests: external,
      report,
    });
    console.log(
      c.name + " [" + vp.name + "]: " + (pass ? "PASS" : "FAIL") +
        (report ? " charts=" + JSON.stringify(report.charts) : " (no report in DOM)") +
        (external.length ? " external=" + JSON.stringify(external) : ""),
    );
  }
  caseResults.push({ case: c.name, fixtures: c.fixtures, receiptClock: c.receipt, viewports });
}

// --- README + BROWSER-MANIFEST.json -------------------------------------------
const readme =
  "# Fixture browser preview — SYNTHETIC, NOT MARKET DATA\n\n" +
  "Generated by `offline/browser-fixture.mjs` (see ADOPT-B2.md). Each\n" +
  "`<case>.html` mounts the REAL dashboard App in a browser DOM from\n" +
  "the handler responses in `responses/<case>.json` (produced by the\n" +
  "real server handlers on the labeled synthetic fixtures), with the\n" +
  "clock frozen at the case's receipt instant and all non-file\n" +
  "network requests blocked. `shots/` holds the desktop (1280x900)\n" +
  "and mobile (390x844) screenshots; `BROWSER-MANIFEST.json` records\n" +
  "the per-case DOM assertion reports, browser/toolchain versions,\n" +
  "and SHA-256 hashes of inputs, fixtures, and outputs.\n";
fs.writeFileSync(path.join(outAbs, "README.md"), readme);
function hashTree(root, files) {
  return files.map((rel) => {
    const buf = fs.readFileSync(path.join(root, rel));
    return { path: rel, bytes: buf.length, sha256: sha256(buf) };
  });
}
const inputFiles = listFiles(spaceRoot);
const fixtureFiles = [...new Set(CASES.flatMap((c) => c.fixtures))].sort();
const outputFiles = listFiles(outAbs, outAbs).filter(
  (f) => f !== "BROWSER-MANIFEST.json",
);
const manifest = {
  generatedBy: "offline/browser-fixture.mjs (fixture-only; no network, no SDK)",
  browser: { path: chromePath, version: chromeVersion },
  toolchain: {
    bun: run("bun", ["--version"]).trim(),
    node: process.version,
    typescript: installedVersion(path.join(workDir, "node_modules", "typescript")),
    tailwindPlugin: installedVersion(path.join(workDir, "node_modules", "bun-plugin-tailwind")),
    fixtureAdapter: adapterVersion,
  },
  network:
    "fixture pages load from file:// URLs — no HTTP server and no IP networking are involved. Chromium's Fetch interception (offline/cdp-drive.mjs) refuses every non-file request (recorded per viewport as externalRequests, asserted zero), and the in-page bootstrap independently traps fetch/XHR and asserts zero attempts. (A loopback HTTP origin was tried first; Chrome 152's Local Network Access checks refuse even the navigation to it in this environment, net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS, so the evidence uses file://.)",
  clock:
    "each page freezes Date at the case's independent receipt instant (see responses/*.json: frozenClock + clockSource from the handler run)",
  viewports: VIEWPORTS.map((v) => v.name + " " + v.w + "x" + v.h),
  cases: caseResults,
  inputs: hashTree(spaceRoot, inputFiles),
  fixturesUsed: fixtureFiles.map((f) => {
    const buf = fs.readFileSync(path.join(fixturesDir, f));
    return { path: f, bytes: buf.length, sha256: sha256(buf) };
  }),
  outputs: hashTree(outAbs, outputFiles),
};
fs.writeFileSync(
  path.join(outAbs, "BROWSER-MANIFEST.json"),
  JSON.stringify(manifest, null, 2) + "\n",
);
if (!keepWork) fs.rmSync(workDir, { recursive: true, force: true });
console.log("BROWSER-MANIFEST.json written; cases failing: " + (anyFail ? "YES" : "none"));
process.exit(anyFail ? 4 : 0);
