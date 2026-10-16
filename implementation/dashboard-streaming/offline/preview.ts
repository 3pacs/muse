// Fixture-only preview harness (run under bun by offline-build.mjs).
//
// Usage: bun run offline/preview.ts <case> <feed_all.json> <signals.json> <outDir>
//
// What it does, with NO network and NO platform SDK:
//   1. Freezes the clock at the fixture's own updated_at + 30s, so the
//      client's freshness math evaluates the frame as its own instant
//      would (documented harness choice, deterministic output).
//   2. Stubs global fetch: /feed/all and /feed/signals return the given
//      SYNTHETIC fixtures; any other URL throws.
//   3. Invokes the REAL server action handlers (server/src/actions.ts)
//      against an in-memory fake ctx.db (drizzle-shaped chain), so the
//      payloads rendered are the production normalize() output.
//   4. Seeds those exact responses into a TanStack QueryClient and
//      server-renders the REAL client App (react-dom/server).
//   5. Writes <case>.html (labeled synthetic preview) and
//      <case>.payload.json (the exact responses the render consumed).
//
// SSR limits, stated plainly: recharts ResponsiveContainer renders an
// empty frame without a DOM, and Tailwind utilities are not compiled in
// the preview — the preview evidences data flow and view-state (status
// pill, panels, labels), not pixel layout.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

const [caseName, feedAllPath, signalsPath, outDir, receiptIso] =
  process.argv.slice(2);
if (!caseName || !feedAllPath || !signalsPath || !outDir) {
  throw new Error(
    "usage: preview.ts <case> <feed_all.json> <signals.json> <outDir> [receiptIso]",
  );
}
const feedAll = JSON.parse(readFileSync(feedAllPath, "utf8"));
const signals = JSON.parse(readFileSync(signalsPath, "utf8"));

// --- frozen clock ----------------------------------------------------------
// ADOPT-B1-R1: the receipt clock is INDEPENDENT of the fixture when one is
// supplied (argv[5]); baseline cases keep the fixture-relative clock
// (fixture updated_at + 30s). An unparseable fixture updated_at falls back
// to the default anchor — the frozen instant is finite by construction, so
// evidence generation can never throw RangeError on adversarial clocks
// (red-team finding B1-R1b).
const DEFAULT_ANCHOR = Date.parse("2026-01-05T14:35:05+00:00");
const fixtureMs =
  typeof feedAll.updated_at === "string"
    ? Date.parse(feedAll.updated_at)
    : NaN;
const receiptMs = receiptIso ? Date.parse(receiptIso) : NaN;
if (receiptIso && !Number.isFinite(receiptMs)) {
  throw new Error("harness: receipt clock is not a valid instant: " + receiptIso);
}
const clockSource = Number.isFinite(receiptMs)
  ? "independent-receipt"
  : Number.isFinite(fixtureMs)
    ? "fixture+30s"
    : "fallback-anchor";
const frozen = Number.isFinite(receiptMs)
  ? receiptMs
  : Number.isFinite(fixtureMs)
    ? fixtureMs + 30_000
    : DEFAULT_ANCHOR + 30_000;
const RealDate = Date;
class FrozenDate extends RealDate {
  constructor(...args: unknown[]) {
    super(...((args.length ? args : [frozen]) as [number]));
  }
  static now(): number {
    return frozen;
  }
}
(globalThis as { Date: unknown }).Date = FrozenDate;

// --- fixture transport -----------------------------------------------------
globalThis.fetch = (async (input: unknown) => {
  const url = String(
    (input as { url?: string })?.url ?? (input as string),
  );
  if (url.includes("/feed/signals")) {
    return new Response(JSON.stringify(signals), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  if (url.includes("/feed/all")) {
    return new Response(JSON.stringify(feedAll), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  throw new Error("fixture adapter: unexpected fetch " + url);
}) as typeof fetch;

// --- in-memory fake ctx.db (drizzle-shaped, thenable chain) ----------------
class FakeQuery implements PromiseLike<unknown[]> {
  constructor(private rows: () => unknown[]) {}
  from(): this {
    return this;
  }
  orderBy(): this {
    return this;
  }
  where(): this {
    return this;
  }
  limit(): this {
    return this;
  }
  then<TResult1 = unknown[], TResult2 = never>(
    onFulfilled?:
      | ((value: unknown[]) => TResult1 | PromiseLike<TResult1>)
      | null,
    onRejected?:
      | ((reason: unknown) => TResult2 | PromiseLike<TResult2>)
      | null,
  ): Promise<TResult1 | TResult2> {
    return Promise.resolve(this.rows()).then(onFulfilled, onRejected);
  }
}
const store: Record<string, unknown>[] = [];
const fakeDb = {
  select: () => new FakeQuery(() => store.slice()),
  insert: () => ({
    values: async (v: Record<string, unknown>) => {
      store.push(v);
    },
  }),
  delete: () => new FakeQuery(() => []),
};
const fakeCtx = { db: <T = unknown>() => fakeDb as unknown as T };

// --- run the real handlers ---------------------------------------------------
const { Actions } = await import("../server/src/actions.ts");
const actions = Actions as unknown as Record<
  string,
  { handler: (ctx: unknown) => Promise<unknown> }
>;
const liveResp = (await actions.getLive.handler(fakeCtx)) as {
  ok: boolean;
  live: { status: string; marketOpen: boolean } | null;
};
const sigResp = (await actions.getSignals.handler(fakeCtx)) as {
  ok: boolean;
};
(globalThis as { __FIXTURE_RESPONSES__?: unknown }).__FIXTURE_RESPONSES__ = {
  getLive: liveResp,
  getSignals: sigResp,
};

// --- render the real App -----------------------------------------------------
const { QueryClient, QueryClientProvider } = await import(
  "@tanstack/react-query"
);
const { renderToString } = await import("react-dom/server");
const React = await import("react");
const { App } = await import("../client/src/App.tsx");

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: Infinity, retry: false } },
});
qc.setQueryData(["live-feed"], liveResp);
qc.setQueryData(["signals-feed"], sigResp);
const bodyHtml = renderToString(
  React.createElement(
    QueryClientProvider,
    { client: qc },
    React.createElement(App),
  ),
);

// --- write outputs -----------------------------------------------------------
mkdirSync(outDir, { recursive: true });
writeFileSync(
  join(outDir, caseName + ".payload.json"),
  JSON.stringify(
    {
      case: caseName,
      synthetic: true,
      feedAllFixture: basename(feedAllPath),
      signalsFixture: basename(signalsPath),
      frozenClock: new RealDate(frozen).toISOString(),
      clockSource,
      getLive: liveResp,
      getSignals: sigResp,
    },
    null,
    2,
  ) + "\n",
);
const html =
  "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n" +
  "<title>SYNTHETIC FIXTURE PREVIEW — " +
  caseName +
  " — NOT MARKET DATA</title>\n</head>\n<body>\n" +
  "<div style=\"background:#7a1f1f;color:#fff;padding:10px 14px;" +
  "font-family:monospace;font-size:13px\">SYNTHETIC FIXTURE PREVIEW — case \"" +
  caseName +
  "\" — driven only by labeled synthetic fixtures (" +
  basename(feedAllPath) +
  " + " +
  basename(signalsPath) +
  "), clock frozen at " +
  new RealDate(frozen).toISOString() +
  ". NOT MARKET DATA. SSR render: charts appear as empty frames; " +
  "Tailwind utilities uncompiled.</div>\n" +
  bodyHtml +
  "\n</body>\n</html>\n";
writeFileSync(join(outDir, caseName + ".html"), html);

// --- view-state assertions (ADOPT-B1-R1) -------------------------------------
// Expectations arrive via OFFLINE_EXPECT_JSON from the entrypoint's case
// table. A mismatch fails the whole build: the preview is evidence only if
// the REAL handler payloads and the REAL rendered view-state match what the
// case claims.
const expect = JSON.parse(process.env.OFFLINE_EXPECT_JSON ?? "{}") as {
  htmlIncludes?: string[];
  htmlExcludes?: string[];
  payloadEquals?: [string, unknown][];
};
const failures: string[] = [];
// React SSR separates dynamic text nodes with <!-- --> markers; strip them
// so assertions match the text a reader sees, not the wire encoding.
const visibleHtml = html.replace(/<!-- -->/g, "");
for (const s of expect.htmlIncludes ?? []) {
  if (!visibleHtml.includes(s)) failures.push("html missing: " + JSON.stringify(s));
}
for (const s of expect.htmlExcludes ?? []) {
  if (visibleHtml.includes(s)) failures.push("html must not contain: " + JSON.stringify(s));
}
const payloadRoot: Record<string, unknown> = {
  getLive: liveResp,
  getSignals: sigResp,
};
for (const [path, want] of expect.payloadEquals ?? []) {
  let cur: unknown = payloadRoot;
  for (const key of path.split(".")) {
    cur = (cur as Record<string, unknown>)?.[key];
  }
  if (cur !== want) {
    failures.push(
      "payload " + path + ": want " + JSON.stringify(want) +
        ", got " + JSON.stringify(cur),
    );
  }
}
if (failures.length) {
  throw new Error(
    "preview " + caseName + " assertions failed:\n  - " + failures.join("\n  - "),
  );
}
console.log(
  "preview " +
    caseName +
    ": getLive.ok=" +
    liveResp.ok +
    " live.status=" +
    (liveResp.live ? liveResp.live.status : "null") +
    " marketOpen=" +
    (liveResp.live ? String(liveResp.live.marketOpen) : "null") +
    " getSignals.ok=" +
    sigResp.ok +
    " htmlBytes=" +
    html.length,
);
