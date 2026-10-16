#!/usr/bin/env node
/**
 * ADOPT-B1-R1 — fixture dependency preparation recipe.
 *
 * Produces a PUBLIC-ONLY node_modules tree for the offline build from an
 * existing installation (e.g. the production space's tree, itself
 * installed from bun.lock), with zero network access:
 *
 *   node offline/prepare-deps.mjs --from <node_modules> --out <dir>
 *
 * What it does:
 *   1. Verifies every dependency in offline/fixture-deps.json is present
 *      in --from at the EXACT locked version (mismatch → exit 3, nothing
 *      is prepared). This is the frozen-install evidence for the tree.
 *   2. Symlinks every package directory from --from into --out EXCEPT the
 *      proprietary `@hatch` scope, which is excluded entirely — the
 *      fixture tree contains no proprietary package; offline-build.mjs
 *      installs the local fixture adapter under that name itself.
 *   3. Writes a receipt next to --out (`<out>.receipt.json`): source,
 *      fixture-lock SHA-256, and the observed version of every locked
 *      dependency.
 *
 * The prepared --out is then passed to offline-build.mjs as --deps,
 * whose own preflight re-attests the same lock before building.
 */
import { createHash } from "node:crypto";
import {
  existsSync, mkdirSync, readdirSync, readFileSync, statSync, symlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  args[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
}
const from = args.from ? resolve(args.from) : null;
const out = args.out ? resolve(args.out) : null;
if (!from || !out) {
  console.error("required: --from <node_modules> --out <dir>");
  process.exit(2);
}
if (!existsSync(from)) {
  console.error("--from does not exist: " + from);
  process.exit(2);
}
const here = dirname(fileURLToPath(import.meta.url));
const lockPath = join(here, "fixture-deps.json");
const lockRaw = readFileSync(lockPath);
const lock = JSON.parse(lockRaw.toString("utf8"));

const observed = {};
const problems = [];
for (const [name, want] of Object.entries(lock.dependencies)) {
  const pkgPath = join(from, name, "package.json");
  if (!existsSync(pkgPath)) {
    problems.push(name + ": missing in source (locked " + want.version + ")");
    continue;
  }
  const got = JSON.parse(readFileSync(pkgPath, "utf8")).version;
  observed[name] = got;
  if (got !== want.version) {
    problems.push(name + ": locked " + want.version + ", source has " + got);
  }
}
if (problems.length) {
  console.error("prepare-deps FAILED (nothing prepared):");
  for (const p of problems) console.error("  - " + p);
  process.exit(3);
}

mkdirSync(out, { recursive: true });
let linked = 0;
for (const name of readdirSync(from)) {
  if (name === ".bin" || name === "@hatch") continue;
  if (!statSync(join(from, name)).isDirectory()) continue;
  symlinkSync(join(from, name), join(out, name), "dir");
  linked++;
}
const receipt = {
  preparedFrom: from,
  fixtureLock: {
    path: "offline/fixture-deps.json",
    sha256: createHash("sha256").update(lockRaw).digest("hex"),
  },
  excluded: [
    "@hatch/* (proprietary platform scope, withheld; the fixture adapter in offline/adapter supplies @hatch/space-sdk at build time)",
  ],
  packageDirsLinked: linked,
  observed,
  preparedAt: new Date().toISOString(),
};
const receiptPath = out + ".receipt.json";
writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
console.log(
  "prepared public-only deps at " + out + " (" + linked +
    " package dirs, " + Object.keys(observed).length +
    " locked versions attested); receipt: " + receiptPath,
);
