// Fixture-only adapter for the @hatch/space-sdk SERVER surface.
//
// The real SDK is a proprietary platform tarball (see package.json) and is
// NOT redistributed here. This stand-in implements exactly the surface the
// dashboard's server actions import, with offline semantics:
//
//   - `z` is re-exported from the public zod package (the same version the
//     SDK itself depends on, per bun.lock).
//   - `defineAction` is the identity function over the same spec shape:
//     the returned definition keeps its `handler`, so the offline harness
//     can invoke the REAL production handlers directly. The platform's
//     runtime request/response schema validation does not happen here —
//     a documented difference.
//   - `Ctx.db` is typed as a schema-generic accessor returning drizzle's
//     LibSQL database type, mirroring the platform's typing so the
//     production sources typecheck unchanged. At runtime the harness
//     supplies an in-memory fake.
//
// Used only by offline/offline-build.mjs in a throwaway working copy.
import { z } from "zod";
import type { LibSQLDatabase } from "drizzle-orm/libsql";

export { z };

export type SpaceDbAccessor = <
  TSchema extends Record<string, unknown> = Record<string, never>,
>() => LibSQLDatabase<TSchema>;

export interface Ctx {
  readonly slug: string;
  readonly invocationId: string;
  readonly spaceDir: string;
  readonly db: SpaceDbAccessor;
  emit(data: unknown): void;
  invalidateQueries(): void;
}

export interface ActionDefinition<
  Req extends z.ZodType = z.ZodType,
  Res extends z.ZodType = z.ZodType,
> {
  readonly request: Req;
  readonly response: Res;
  readonly handler: (
    ctx: Ctx,
    args: z.infer<Req>,
  ) => Promise<z.infer<Res>>;
}

export function defineAction<
  Req extends z.ZodType,
  Res extends z.ZodType,
>(spec: ActionDefinition<Req, Res>): ActionDefinition<Req, Res> {
  return spec;
}

export type ActionsModule = Record<
  string,
  Omit<ActionDefinition, "handler"> & {
    handler: (ctx: Ctx, args: never) => Promise<unknown>;
  }
>;
