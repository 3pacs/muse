-- ADOPT-C1-R1: chronological snapshot identity.
-- Adds the validated-UTC-instant key (epoch milliseconds) for the
-- snapshots table and backfills it from the stored `updated_at` text.
-- Additive and provenance-preserving: no row is deleted, merged or
-- rewritten; `updated_at` and `payload_json` keep their original bytes,
-- including legacy rows that spell one instant with different timezone
-- offsets. Rows whose timestamp does not parse leave instant_ms NULL;
-- the application treats those as never-newest and prunes them first.
ALTER TABLE snapshots ADD COLUMN instant_ms INTEGER;
--> statement-breakpoint
UPDATE snapshots SET instant_ms = CAST(ROUND(unixepoch(updated_at, 'subsec') * 1000) AS INTEGER) WHERE instant_ms IS NULL AND unixepoch(updated_at) IS NOT NULL;
--> statement-breakpoint
CREATE INDEX snapshots_instant_idx ON snapshots (instant_ms);
