import { integer, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const entries = sqliteTable("entries", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  text: text("text").notNull(),
  createdAt: integer("created_at", { mode: "timestamp_ms" })
    .notNull()
    .$defaultFn(() => new Date()),
});

/**
 * One row per interpreter snapshot persisted while the dashboard is open.
 * Keyed by the payload's own `updated_at` (UTC instant from the interpreter),
 * deduped on that value. Full payload kept so the trail and detail views
 * share one source. Pruned to the most recent ~3 trading days of rows.
 */
export const snapshots = sqliteTable("snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  updatedAt: text("updated_at").notNull().unique(),
  spot: real("spot"),
  maxPain: real("max_pain"),
  callWall: real("call_wall"),
  putWall: real("put_wall"),
  gammaFlip: real("gamma_flip"),
  netGexM: real("net_gex_m"),
  pinScore: real("pin_score"),
  expectedMove: real("expected_move"),
  regime: text("regime"),
  payloadJson: text("payload_json").notNull(),
  createdAt: integer("created_at", { mode: "timestamp_ms" })
    .notNull()
    .$defaultFn(() => new Date()),
});
