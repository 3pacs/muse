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
 * The payload's own `updated_at` string is preserved verbatim (provenance)
 * and stays unique per stored spelling, but observation IDENTITY is the
 * validated UTC instant: `instant_ms` (added by migration 0003, backfilled
 * from `updated_at`) is the single chronological key for dedupe, latest
 * selection, the persistence-gap comparison, trail ordering and retention
 * (ADOPT-C1-R1). Two spellings of one instant (Z vs an equivalent numeric
 * offset) are one observation. `instant_ms` is null only on legacy rows
 * whose stored timestamp does not parse as a timezone-aware instant; such
 * rows are never selected as the newest and prune first. Full payload kept
 * so the trail and detail views share one source. Pruned to the newest
 * 1500 observations by instant.
 */
export const snapshots = sqliteTable("snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  updatedAt: text("updated_at").notNull().unique(),
  instantMs: integer("instant_ms"),
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
