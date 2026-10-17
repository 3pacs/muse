#!/usr/bin/env node
/**
 * ADOPT-C1 — offline snapshot persistence/fallback audit entrypoint.
 *
 * One command that, with NO network, NO platform SDK, NO real feed and
 * NO production database:
 *   1. copies this dashboard tree into a throwaway working directory,
 *   2. assembles node_modules from a caller-supplied, lockfile-installed
 *      dependency tree (--deps), substituting ONLY @hatch/space-sdk with
 *      the fixture-only adapter in offline/adapter/ (same assembly as
 *      offline-build.mjs),
 *   3. runs offline/snapshot-audit-entry.ts under bun: the REAL
 *      server/src/actions.ts getLive handler + REAL schema + REAL
 *      drizzle/0002 DDL over drizzle-orm/libsql on in-memory storage,
 *      with global fetch replaced by an in-memory stub,
 *   4. leaves snapshot-audit-receipt.json + fixtures/ in --out.
 *
 * Usage:
 *   node offline/snapshot-audit.mjs --deps <node_modules> --out <dir>
 *     [--work <dir>] [--space <dir>]
 *
 * --deps must be a node_modules tree installed from this package's
 * bun.lock (e.g. the production space's own install). Nothing is
 * downloaded; a missing --deps is a hard error, not an install trigger.
 * Exit code: 0 when the audit harness itself completed (case verdicts
 * — including COUNTEREXAMPLE — are reported in the receipt, not via
 * the exit code); non-zero only on harness/assembly failure.
 */
import { execFileSync } from "node:child_process";
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync,
  statSync, symlinkSync,
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
if (!deps || !out) {
  console.error("required: --deps <node_modules> --out <dir>");
  process.exit(2);
}
if (!existsSync(deps)) {
  console.error("--deps does not exist: " + deps + " (no downloads are performed)");
  process.exit(2);
}
const work = args.work ? resolve(args.work) : mkdtempSync(join(tmpdir(), "adopt-c1-"));
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const EXCLUDE = (rel, name) =>
  ["node_modules", ".bun-cache", ".space-build", "offline-out", "preview"].includes(name) ||
  rel.startsWith(join("client", "dist")) ||
  rel.startsWith(join("server", "dist"));

// 1 — working copy
mkdirSync(work, { recursive: true });
cpSync(space, work, {
  recursive: true,
  filter: (src) => !EXCLUDE(relative(space, src), src.split("/").pop()),
});

// 2 — node_modules: real deps, SDK replaced by the fixture adapter
// (unconditional install, per the ADOPT-B1-R1 lesson).
const nm = join(work, "node_modules");
mkdirSync(nm, { recursive: true });
for (const name of readdirSync(deps)) {
  if (name === ".bin" || name === "@hatch") continue;
  if (!statSync(join(deps, name)).isDirectory()) continue;
  symlinkSync(join(deps, name), join(nm, name), "dir");
}
const hatchDir = join(nm, "@hatch");
mkdirSync(hatchDir, { recursive: true });
const depsHatch = join(deps, "@hatch");
if (existsSync(depsHatch)) {
  for (const child of readdirSync(depsHatch)) {
    if (child === "space-sdk") continue;
    symlinkSync(join(depsHatch, child), join(hatchDir, child), "dir");
  }
}
symlinkSync(join(work, "offline", "adapter"), join(hatchDir, "space-sdk"), "dir");

// 2b — attest the versions this audit actually exercises + prove the
// working copy's exercised sources are byte-identical to the package's.
const exercised = [
  "server/src/actions.ts",
  "server/src/schema.ts",
  "drizzle/0002_snapshots_table.sql",
  "offline/snapshot-audit-entry.ts",
  "offline/snapshot-audit.mjs",
];
for (const rel of exercised) {
  const a = sha256(readFileSync(join(space, rel)));
  const b = sha256(readFileSync(join(work, rel)));
  if (a !== b) {
    console.error("working copy differs from package source: " + rel);
    process.exit(3);
  }
}
const versions = {};
for (const name of ["drizzle-orm", "@libsql/client", "zod", "typescript"]) {
  const p = join(nm, name, "package.json");
  versions[name] = existsSync(p) ? JSON.parse(readFileSync(p, "utf8")).version : null;
}
console.log("snapshot audit assembly OK; dependency versions:", JSON.stringify(versions));

// 3 — run the audit entry under bun
mkdirSync(out, { recursive: true });
execFileSync("bun", ["run", join(work, "offline", "snapshot-audit-entry.ts"), out], {
  stdio: "inherit",
  cwd: work,
});
console.log("\nADOPT-C1 snapshot audit complete; receipt in " + out);
