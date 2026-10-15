CREATE TABLE snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  updated_at TEXT NOT NULL UNIQUE,
  spot REAL,
  max_pain REAL,
  call_wall REAL,
  put_wall REAL,
  gamma_flip REAL,
  net_gex_m REAL,
  pin_score REAL,
  expected_move REAL,
  regime TEXT,
  payload_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
--> statement-breakpoint
CREATE INDEX snapshots_updated_at_idx ON snapshots (updated_at);
