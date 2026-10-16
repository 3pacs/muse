// Fixture-only adapter for @hatch/space-sdk/build.
//
// The real buildClient() owns the production bundle configuration
// (Bun.build + the SDK's Tailwind plugin, canonical asset naming). This
// stand-in performs a plain Bun.build of the same entrypoint so the
// client compiles and bundles offline against the public dependencies.
// Deliberate differences from production: Tailwind utilities are NOT
// compiled (the emitted CSS is the unprocessed source), and asset names
// are the simple [name] pattern. Output directory: $OFFLINE_CLIENT_OUT
// or ./offline-out/client relative to the working copy root.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export async function buildClient(): Promise<void> {
  const root = process.cwd();
  const outdir =
    process.env.OFFLINE_CLIENT_OUT ?? join(root, "offline-out", "client");
  mkdirSync(outdir, { recursive: true });
  const result = await Bun.build({
    entrypoints: [join(root, "client", "src", "main.tsx")],
    outdir,
    target: "browser",
  });
  if (!result.success) {
    for (const log of result.logs) console.error(log);
    throw new Error("fixture adapter: offline client build failed");
  }
  const entry = result.outputs.find((o) => o.kind === "entry-point");
  const entryName = entry ? entry.path.split("/").pop() ?? "main.js" : "main.js";
  const css = result.outputs.find((o) => o.path.endsWith(".css"));
  const cssName = css ? css.path.split("/").pop() ?? "main.css" : null;
  let html = readFileSync(join(root, "client", "index.html"), "utf8");
  html = html.replace("./src/main.tsx", "./" + entryName);
  if (cssName) {
    html = html.replace(
      "</head>",
      '    <link rel="stylesheet" href="./' + cssName + '" />\n  </head>',
    );
  }
  writeFileSync(join(outdir, "index.html"), html);
}
