# DEPLOY ORDER — /gex/ public feed routes on stepdadfi.com (rev4 sealed package)

**Authority:** Anik's direct order in his main Muse chat, 2026-10-20 18:18 PT ("deploy"), executing his standing selection: **PUBLIC `stepdadfi.com/gex/` with exactly two same-origin GETs — `/gex/feed/all` and `/gex/feed/signals` — site root preserved.** Issued by Muse MAIN (producer owner) to the server agent that owns the box behind stepdadfi.com / gex.stepdad.finance.

**Payload:** `interpreter.py` in this folder — the rev4 sealed interpreter, SHA-256 `cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0` (seal manifest: `SEAL-MANIFEST.sha256`, manifest file `7e2c3ff3…`). This is the public-safe variant of the live producer (pin `b95d1c3c…`): public error payloads never echo exception text, stored signal detail is typed-screened, non-finite numerics are rejected, payloads serialize under `allow_nan=False`. Verified SOUND by the red-team reviewer with no residual blockers (rev4 review, 2026-10-19). The envelope contract it serves is the corrected rev2 schema in `docs/muse-main-producer-20261020-rev2/` (status variants ok/error/quarantined/starting; consumers gate on `status == "ok"`; `updated_at` is build-start time).

## Install spec

1. **Release root (proposed; confirm against the box and report any deviation):** `/data/agent-home/anikdang/muse-0dte/releases/rev4-cb4f0ef2/` holding the payload file byte-identical to the hash above. **Data root:** `/data/agent-home/anikdang/muse-0dte-data/`.
2. **One porting change only:** repoint the `TAPE_DB` constant from the Muse-VM path to `<data root>/tape.db`. Nothing else in the file changes; the installed file's diff against the payload must be exactly that one constant. `/feed/signals` opens the DB read-only; if no server-side tape.db exists yet, signals returns its honest error/empty shape — that is acceptable for this deploy and must not be "fixed" by copying Muse's VM database.
3. **Loopback only:** run with `--port 8788` bound to 127.0.0.1. Port 8787 on this box is an unrelated network dashboard — do not touch it.
4. **Supervision (required):** run under the supervisor pattern (systemd `Restart=always` or the bundled `run_interpreter.sh` equivalent) — never the bare interpreter; it must restart within ~10 s of any exit, with exits logged (append, never truncate).
5. **Proxy — exactly two routes, nothing else:** `GET /gex/feed/all` → `127.0.0.1:8788/feed/all`; `GET /gex/feed/signals` → `127.0.0.1:8788/feed/signals`. No other methods, no other paths, no directory listing. **The site root and every existing route stay byte-for-byte as they are** (the apex currently serves the GRID app; `/gex/*` currently falls back to the SPA — after this deploy only those two exact paths change behavior).
6. **Inputs:** the interpreter polls this box's own collector (`http://gex.stepdad.finance/api/state`, `/api/contracts`) and the public Nasdaq chain API — no new credentials, no new accounts, no DNS changes, no auth changes.

## Explicit non-goals (do not do)

- No watcher/EOD/alerting jobs from the sealed lineage — never enable them in this lane.
- No dashboard page in this deploy (feeds only); no changes to grid.stepdad.finance; no other stepdadfi.com paths.
- No second interpreter instance against any shared tape.db.

## Verification + receipt (required back on PR #2)

1. Installed-file hash + the one-line TAPE_DB diff.
2. Service/supervisor status and a kill-test result (PID killed → restarted ≤ ~10 s, exit logged).
3. From the box: `curl -s 127.0.0.1:8788/feed/all` status field + spot during market hours; `/feed/signals` response shape.
4. Public: `https://stepdadfi.com/gex/feed/all` and `/gex/feed/signals` return JSON (not the SPA HTML), and `https://stepdadfi.com/` is unchanged.
5. **Rollback** if any check fails: remove the two proxy routes and stop the service; nothing else was touched, so nothing else needs restoring. Report the failure instead of improvising a fix.

Until the receipt lands and the public checks pass, the live site is **not** to be described as recovered.
