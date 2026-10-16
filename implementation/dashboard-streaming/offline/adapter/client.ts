// Fixture-only adapter for the @hatch/space-sdk/client surface.
//
// Implements exactly what the dashboard client imports, with the same
// type-level contract as the platform (action request/response types are
// inferred from the zod schemas via the action definitions):
//   - `createActionClient` — instead of POSTing to the platform, returns
//     a proxy whose methods resolve to the fixture-driven responses the
//     offline harness seeded on `globalThis.__FIXTURE_RESPONSES__` (those
//     responses are produced by the REAL server handlers running on the
//     synthetic fixtures — see ../preview.ts).
//   - `spaceQueryClient` — a plain TanStack QueryClient.
//   - `SafeAreaTopScrim` — renders nothing in the preview (the real one
//     draws a safe-area gradient; cosmetic only, no data semantics).
import { QueryClient } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import type { z } from "zod";

export const spaceQueryClient = new QueryClient();

export interface ClientActionShape {
  request: z.ZodType;
  response: z.ZodType;
}

export type ActionRequest<A extends { request: z.ZodType }> = z.infer<
  A["request"]
>;
export type ActionResponse<A extends { response: z.ZodType }> = z.infer<
  A["response"]
>;

export type ActionClient<A extends Record<string, ClientActionShape>> = {
  [K in keyof A]: (
    args: ActionRequest<A[K]>,
  ) => Promise<ActionResponse<A[K]>>;
};

export type ApiRequest<
  C extends Record<string, (args: never) => Promise<unknown>>,
  K extends keyof C,
> = Parameters<C[K]>[0];

export type ApiResponse<
  C extends Record<string, (args: never) => Promise<unknown>>,
  K extends keyof C,
> = Awaited<ReturnType<C[K]>>;

export function createActionClient<
  A extends Record<string, ClientActionShape>,
>(): ActionClient<A> {
  const proxy = new Proxy(
    {},
    {
      get:
        (_target, prop) =>
        async (): Promise<unknown> => {
          const all =
            (globalThis as { __FIXTURE_RESPONSES__?: Record<string, unknown> })
              .__FIXTURE_RESPONSES__ ?? {};
          const seeded = all[prop as string];
          if (seeded === undefined) {
            throw new Error(
              "fixture adapter: no seeded response for action " +
                String(prop),
            );
          }
          return seeded;
        },
    },
  );
  return proxy as ActionClient<A>;
}

export interface SafeAreaTopScrimProps {
  variant?: "gradient" | "blur" | "solid";
  backgroundColor?: CSSProperties["backgroundColor"];
  zIndex?: CSSProperties["zIndex"];
  className?: string;
  style?: CSSProperties;
}

export function SafeAreaTopScrim(_props: SafeAreaTopScrimProps): null {
  return null;
}
