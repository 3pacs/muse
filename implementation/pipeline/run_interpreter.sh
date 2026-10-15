#!/usr/bin/env bash
# Supervisor for the 0DTE interpreter.
#
# Why this exists (2026-10-14): the interpreter died at least twice during the
# session (tape gap 08:42-09:12 PT, plus an earlier pre-open death) and each
# outage lasted ~30 minutes, because the only auto-restart lived inside the
# 2-minute *agent* cron (0dte-early-warning / 0dte-maxpain-log step 1) — and
# those agent runs coalesce and back up when the runtime is busy. This loop is
# dumb and fast: if the interpreter process exits for any reason, it restarts
# it within RESTART_DELAY seconds, and every exit is logged WITH its exit code
# and any traceback (append-only, so crash evidence survives restarts — the
# 2026-10-14 deaths left no trace because the old start command used '>').
#
# Usage:
#   nohup ./run_interpreter.sh >>/tmp/0dte-interp.log 2>&1 &
# Stop:
#   kill the supervisor PID (pgrep -f run_interpreter.sh); it kills its child.
#
# It does NOT touch an interpreter that is already running under a different
# parent — check `pgrep -af interpreter.py` before starting it, and only
# adopt it at a planned restart (e.g. after the close), never mid-session
# alongside the existing plain-nohup instance.

set -u
cd "$(dirname "$0")"

PORT="${INTERPRETER_PORT:-8787}"
POLL="${INTERPRETER_POLL:-30}"
RESTART_DELAY="${RESTART_DELAY:-5}"
LOG_PREFIX="[supervisor]"

child=""
cleanup() {
  echo "$LOG_PREFIX $(date -Is) stopping; killing child ${child:-none}"
  [ -n "$child" ] && kill "$child" 2>/dev/null
  exit 0
}
trap cleanup TERM INT

while true; do
  echo "$LOG_PREFIX $(date -Is) starting interpreter on :$PORT (poll ${POLL}s)"
  python3 interpreter.py --port "$PORT" --poll "$POLL" &
  child=$!
  wait "$child"
  code=$?
  child=""
  echo "$LOG_PREFIX $(date -Is) interpreter exited with code $code; restarting in ${RESTART_DELAY}s"
  sleep "$RESTART_DELAY"
done
