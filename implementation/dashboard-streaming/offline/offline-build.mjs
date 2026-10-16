#!/usr/bin/env node
/**
 * ADOPT-B1 — dependency-locked offline build + fixture preview entrypoint.
 *
 * One command that, with NO network and NO platform SDK:
 *   1. copies this dashboard tree into a throwaway working directory,
 *   2. assembles node_modules from a caller-supplied, lockfile-installed
 *      dependency tree (--deps), substituting ONLY @hatch/space-sdk with
 *      the fixture-only adapter in offline/adapter/,
 *   3. runs the ADOPT-F1 boundary tests and both TypeScript project
 *      checks against the working copy,
 *   4. builds the server bundle (bun build) and the client bundle (via
 *      the adapter's buildClient),
 *   5. renders four synthetic-fixture previews (success, last-session,
 *      legacy-tags, error) through the REAL handlers + REAL App,
 *   6. writes BUILD-MANIFEST.json mapping every source input to every
 *      output by SHA-256, with the exact toolchain versions recorded.
 *
 * Usage:
 *   node offline/offline-build.mjs --deps <node_modules> --out <dir>
 *     [--work <dir>] [--fixtures <dir>] [--space <dir>]
 *
 * --deps must be a node_modules tree installed from this package's
 * bun.lock (e.g. the production space's own install). Nothing is
 * downloaded; a missing --deps is a hard error, not an install trigger.
 */
import { execFileSync } from "node:child_process";
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync,
  statSync, symlinkSync, writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  args[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
}
const space = resolve(args.space ?? join(dirname(fileURLToPath(import.meta.url)), ".."));
const deps = args.deps ? resolve(args.deps) : null;
const out = args.out ? resolve(args.out) : null;
const fixtures = resolve(args.fixtures ?? join(space, "..", "fixtures"));
if (!deps || !out) {
  console.error("required: --deps <node_modules> --out <dir>");
  process.exit(2);
}
if (!existsSync(deps)) {
  console.error("--deps does not exist: " + deps + " (no downloads are performed)");
  process.exit(2);
}
const work = args.work ? resolve(args.work) : mkdtempSync(join(tmpdir(), "adopt-b1-"));
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

function run(step, cmd, cmdArgs, opts = {}) {
  process.stdout.write("\n=== " + step + " ===\n");
  execFileSync(cmd, cmdArgs, { stdio: "inherit", ...opts });
}
function listFiles(root, exclude) {
  const found = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const p = join(dir, name);
      const rel = relative(root, p);
      if (exclude(rel, name)) continue;
      if (statSync(p).isDirectory()) walk(p);
      else found.push(rel);
    }
  };
  walk(root);
  return found;
}
const EXCLUDE = (rel, name) =>
  ["node_modules", ".bun-cache", ".space-build", "offline-out"].includes(name) ||
  rel.startsWith(join("client", "dist")) ||
  rel.startsWith(join("server", "dist"));

// 1 — working copy -----------------------------------------------------------
mkdirSync(work, { recursive: true });
cpSync(space, work, {
  recursive: true,
  filter: (src) => !EXCLUDE(relative(space, src), src.split("/").pop()),
});

// 2 — node_modules: real deps, SDK replaced by the fixture adapter ----------
const nm = join(work, "node_modules");
mkdirSync(nm, { recursive: true });
for (const name of readdirSync(deps)) {
  if (name === ".bin") continue;
  if (name === "@hatch") {
    const scopeDir = join(nm, "@hatch");
    mkdirSync(scopeDir, { recursive: true });
    for (const child of readdirSync(join(deps, "@hatch"))) {
      if (child === "space-sdk") continue;
      symlinkSync(join(deps, "@hatch", child), join(scopeDir, child), "dir");
    }
    symlinkSync(join(work, "offline", "adapter"), join(scopeDir, "space-sdk"), "dir");
  } else {
    symlinkSync(join(deps, name), join(nm, name), "dir");
  }
}
// The client tsconfig maps @space/privileged to a platform-generated
// contract that lives only in a built space. Copy it from the reference
// environment (the tree --deps came from) when present; it is recorded
// in the manifest as environment-provided, never as candidate source.
const refSpace = dirname(deps);
const genDir = join(refSpace, "server", ".generated");
const hasGenerated = existsSync(genDir);
if (hasGenerated) {
  cpSync(genDir, join(work, "server", ".generated"), { recursive: true });
}

// 3 — tests + typecheck --------------------------------------------------------
run("boundary tests (ADOPT-F1)", process.execPath, [join(work, "tests", "boundaries.test.mjs")]);
const tscBin = join(deps, "typescript", "bin", "tsc");
run("typecheck client", process.execPath, [tscBin, "-p", join(work, "client", "tsconfig.json"), "--noEmit"]);
run("typecheck server", process.execPath, [tscBin, "-p", join(work, "server", "tsconfig.json"), "--noEmit"]);

// 4 — builds -------------------------------------------------------------------
mkdirSync(join(out, "server"), { recursive: true });
run("server bundle (bun build)", "bun", [
  "build", join(work, "server", "src", "actions.ts"),
  "--target=bun", "--outfile", join(out, "server", "actions.js"),
]);
run("client bundle (adapter buildClient)", "bun", ["./client/build.mjs"], {
  cwd: work,
  env: { ...process.env, OFFLINE_CLIENT_OUT: join(out, "client") },
});

// 5 — fixture previews -----------------------------------------------------------
const CASES = [
  ["success", "feed_all_success.json", "feed_signals_success.json"],
  ["last-session", "feed_all_last_session.json", "feed_signals_success.json"],
  ["legacy", "feed_all_success.json", "feed_signals_legacy_tags.json"],
  ["clustering", "feed_all_success.json", "feed_signals_cluster_true.json"],
  ["error", "feed_all_error.json", "feed_signals_error.json"],
];
for (const [name, feedAll, signals] of CASES) {
  run("preview " + name, "bun", [
    "run", join(work, "offline", "preview.ts"), name,
    join(fixtures, feedAll), join(fixtures, signals), join(out, "preview"),
  ], { cwd: work });
}

// 6 — build manifest -------------------------------------------------------------
const bunVersion = execFileSync("bun", ["--version"], { encoding: "utf8" }).trim();
const tsVersion = JSON.parse(readFileSync(join(deps, "typescript", "package.json"), "utf8")).version;
const pkg = JSON.parse(readFileSync(join(space, "package.json"), "utf8"));
const inputs = listFiles(space, EXCLUDE).map((rel) => {
  const data = readFileSync(join(space, rel));
  return { path: rel, bytes: data.length, sha256: sha256(data) };
});
const outputs = listFiles(out, () => false)
  .filter((rel) => rel !== "BUILD-MANIFEST.json")
  .map((rel) => {
    const data = readFileSync(join(out, rel));
    return { path: rel, bytes: data.length, sha256: sha256(data) };
  });
const manifest = {
  generatedBy: "implementation/dashboard-streaming/offline/offline-build.mjs",
  synthetic: "previews are driven only by labeled synthetic fixtures",
  toolchain: {
    bun: bunVersion,
    node: process.version,
    typescript: tsVersion,
    packageManagerDeclared: pkg.packageManager ?? null,
  },
  lockfile: {
    path: "bun.lock",
    sha256: sha256(readFileSync(join(space, "bun.lock"))),
    lockfileVersion: 2,
  },
  dependenciesExact: { ...pkg.dependencies, ...pkg.devDependencies },
  fixturesUsed: [...new Set(CASES.flatMap((c) => [c[1], c[2]]))].map((name) => {
    const data = readFileSync(join(fixtures, name));
    return { path: "implementation/fixtures/" + name, bytes: data.length, sha256: sha256(data) };
  }),
  environmentProvided: hasGenerated
    ? ["server/.generated/privileged.contract (platform-generated; copied from the reference install for the typecheck only; not candidate source)"]
    : [],
  inputs,
  outputs,
};
writeFileSync(join(out, "BUILD-MANIFEST.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(
  "\nADOPT-B1 offline build complete: " + inputs.length + " inputs, " +
  outputs.length + " outputs, manifest at " + join(out, "BUILD-MANIFEST.json"),
);
