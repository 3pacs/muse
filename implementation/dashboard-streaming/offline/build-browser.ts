// Fixture-only browser bundle build (ADOPT-B2). Run by browser-fixture.mjs
// inside the assembled work copy, under Bun:
//
//   OFFLINE_BROWSER_OUT=<dir> bun run offline/build-browser.ts
//
// Builds the REAL dashboard client for a browser target: the fixture
// bootstrap (offline/browser-entry.tsx) mounts client/src/App, and the
// production theme.css is compiled by bun-plugin-tailwind — the same
// Tailwind plugin the production SDK build uses. The proprietary SDK is
// not involved: "@hatch/space-sdk" resolves to the fixture adapter.
import tailwindPlugin from "bun-plugin-tailwind";

const out = process.env.OFFLINE_BROWSER_OUT;
if (!out) throw new Error("OFFLINE_BROWSER_OUT is required");

const result = await Bun.build({
  entrypoints: ["offline/browser-entry.tsx"],
  outdir: out,
  target: "browser",
  plugins: [tailwindPlugin],
});

if (!result.success) {
  for (const log of result.logs) console.error(log);
  process.exit(1);
}
for (const o of result.outputs) {
  console.log("OUTPUT", o.kind, o.path, o.size);
}
