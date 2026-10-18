#!/usr/bin/env node
/**
 * ADOPT-C1-R1 — chronological snapshot identity regression entrypoint.
 *
 * One command that, with NO network, NO platform SDK, NO real feed and
 * NO production database:
 *   1. copies this dashboard tree into a throwaway working directory,
 *   2. assembles node_modules from a caller-supplied, lockfile-installed
 *      dependency tree (--deps), substituting ONLY @hatch/space-sdk with
 *      the fixture-only adapter in offline/adapter/ (same assembly as
 *      offline-build.mjs and snapshot-audit.mjs),
 *   3. runs offline/snapshot-audit-r1-entry.ts under bun: the REAL
 *      server/src/actions.ts getLive handler (C1-R1 revision) + REAL
 *      schema + verbatim 0002/0003 DDL over drizzle-orm/libsql on
 *      in-memory storage, with global fetch replaced by a stub,
 *   4. writes a receipt JSON (--receipt, default <out>/receipt.json)
 *      binding the case verdicts to the exercised file hashes.
 *
 * Usage:
 *   node offline/snapshot-audit-r1.mjs --deps <node_modules> --out <dir>
 *     [--receipt <path>] [--work <dir>] [--space <dir>]
 *
 * Exit code: 0 only when every regression case PASSes; non-zero on any
 * FAIL or harness/assembly failure. (Unlike the C1 audit, this harness
 * verifies a fix, so a failed expectation is a failed run.)
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
if (!deps || !out) {
  console.error("required: --deps <node_modules> --out <dir>");
  process.exit(2);
}
if (!existsSync(deps)) {
  console.error("--deps does not exist: " + deps + " (no downloads are performed)");
  process.exit(2);
}
const work = args.work ? resolve(args.work) : mkdtempSync(join(tmpdir(), "adopt-c1r1-"));
const receiptPath = args.receipt ? resolve(args.receipt) : join(out, "receipt.json");
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

// 2b — attest exercised sources byte-identical between package and work
const exercised = [
  "server/src/actions.ts",
  "server/src/schema.ts",
  "drizzle/0002_snapshots_table.sql",
  "drizzle/0003_snapshot_instant.sql",
  "offline/snapshot-audit-r1-entry.ts",
  "offline/snapshot-audit-r1.mjs",
];
const fileHashes = {};
for (const rel of exercised) {
  const a = sha256(readFileSync(join(space, rel)));
  const b = sha256(readFileSync(join(work, rel)));
  if (a !== b) {
    console.error("working copy differs from package source: " + rel);
    process.exit(3);
  }
  fileHashes[rel] = a;
}
const versions = {};
for (const name of ["drizzle-orm", "@libsql/client", "zod", "typescript"]) {
  const p = join(nm, name, "package.json");
  versions[name] = existsSync(p) ? JSON.parse(readFileSync(p, "utf8")).version : null;
}
const bunVersion = execFileSync("bun", ["--version"], { encoding: "utf8" }).trim();
console.log("C1-R1 regression assembly OK; dependency versions:", JSON.stringify(versions));

// 3 — run the regression entry under bun
mkdirSync(out, { recursive: true });
execFileSync("bun", ["run", join(work, "offline", "snapshot-audit-r1-entry.ts"), out], {
  stdio: "inherit",
  cwd: work,
});
const casesDoc = JSON.parse(readFileSync(join(out, "r1-cases.json"), "utf8"));
const failed = casesDoc.cases.filter((c) => c.verdict !== "PASS");
const receipt = {
  assignment: "ADOPT-C1-R1",
  base: "ADOPT-C1 audit pin 2eb8159deac1061da12af58540c14757be11bbf5",
  mode: "real getLive handler + real schema + verbatim 0002/0003 DDL on drizzle-orm/libsql in-memory storage; SDK adapter + fetch stub substitutions as disclosed in the entry header",
  runtime: { bun: bunVersion, node: process.version },
  dependencyVersions: versions,
  fileHashes,
  summary: {
    cases: casesDoc.cases.length,
    pass: casesDoc.cases.length - failed.length,
    fail: failed.length,
  },
  cases: casesDoc.cases,
};
mkdirSync(dirname(receiptPath), { recursive: true });
writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
console.log(
  "\nADOPT-C1-R1 regressions: " + receipt.summary.pass + "/" + receipt.summary.cases +
    " PASS; receipt at " + receiptPath,
);
process.exit(failed.length ? 1 : 0);
