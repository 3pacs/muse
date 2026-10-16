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

const [caseName, feedAllPath, signalsPath, outDir] = process.argv.slice(2);
if (!caseName || !feedAllPath || !signalsPath || !outDir) {
  throw new Error(
    "usage: preview.ts <case> <feed_all.json> <signals.json> <outDir>",
  );
}
const feedAll = JSON.parse(readFileSync(feedAllPath, "utf8"));
const signals = JSON.parse(readFileSync(signalsPath, "utf8"));

// --- frozen clock ----------------------------------------------------------
const anchor =
  typeof feedAll.updated_at === "string"
    ? Date.parse(feedAll.updated_at)
    : Date.parse("2026-01-05T14:35:05+00:00");
const frozen = anchor + 30_000;
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
