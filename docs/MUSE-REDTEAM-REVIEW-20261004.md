# Muse second red-team handoff — 2026-10-04

**Verdict: PROVISIONAL; Stage 1/2 acceptance remains blocked.** The patch makes useful changes, but the offline fixtures below still violate the first challenge. This document publishes review evidence and acceptance requirements only. It does not change application source, authorize activation, merge, deployment, trading, or establish predictive value.

## Source and evidence boundary

- Reviewed [Muse `ed3b8741c21b58438be1da65a1dca17d0c5e3bac`](https://github.com/3pacs/muse/tree/ed3b8741c21b58438be1da65a1dca17d0c5e3bac), `redteam/fixes`, exactly four commits after [original main `43c2cd41f3823adcda5222d4648131a374c47a59`](https://github.com/3pacs/muse/tree/43c2cd41f3823adcda5222d4648131a374c47a59). Changed source: interpreter, logger, tape database, dashboard builder.
- Acceptance reference: [first challenge at `16b1d4a4261591811c24b679196360e4182f5caf`](https://github.com/3pacs/muse/blob/16b1d4a4261591811c24b679196360e4182f5caf/docs/MUSE-CHALLENGE.md), draft [PR #1](https://github.com/3pacs/muse/pull/1). This second report supplements it; it does not replace its stages or redefine a failed assertion.
- Independent Dell/Linux rerun: **21 named checks: 10 pass, 11 fail**, Python 3.14.4, standard library only. These are synthetic contract checks, not an existing project test suite. No tests, AGENTS.md, .agents skills, raw history, or frontend artifacts are tracked at the reviewed head.
- Imported source definitions with `__name__` different from `__main__`; did not run service/poll/alert entrypoints. Network calls were blocked; fetches and clocks were synthetic. All writes and SQLite stores were disposable. Logger recovery ran in separate real Python processes with real POSIX `fcntl`, including a tested contention guard; no Windows lock stub was used.
- Fixtures use `2026-10-05` as a synthetic session and a fixed clock; they are not market observations. No provider access, ingestion, deployment, production write, order or notification occurred. Earlier Lenovo results are corroborating context; all counts here come from the appended Dell harness.
- Source inspection is separate from runtime acceptance. No deployed GRID payload/revision, data rights, raw 78-snapshot history, visual UI, or incremental-value claim was verified. The harness tests only the specified cases and is not a full financial-model certification.

## Improvements supported by this run

| Change | Actual evidence | Limit |
| --- | --- | --- |
| F04 GEX scale | Same `S=100`, gamma `.02`, OI `100`, multiplier `100` fixture: original output `2.0` million; patch `.02` million, matching USD per 1% move. | Mixed historical formula versions still need an explicit projection policy. |
| F06 charm | Six independent delta finite-difference samples (call/put, K 90/100/110, T=.01, sigma=.2, r=.043, q=.013): maximum absolute error falls from `.04299440844` to `6.62953e-10`, below frozen `1e-7` tolerance. Source converts annual decay by `365.25*24` and applies opposite hedge sign. | Sampled derivative checks do not certify aggregation, all scenarios, or near-expiry conditioning. |
| F02 cache | Forced refresh failure discards same-date wings at age 1801 seconds and previous-date wings at age 1 second. | Cache receipt time still is not vendor source time; calendar/skew gates remain unaccepted. |
| F07 RR | Available deltas +.5/-.5 return null RR rather than a mislabeled 25-delta pair. | Actual selected deltas and rejection reasons are not exposed. |
| F08 names | Activity keys are `elevated_volume_activity` and `top_volume_activity`, with unsigned-activity copy. | Logger/dashboard still need to retain interpretation metadata; current-mid volume proxy is not historical executed notional. |
| F09/F10 persistence | Logger now imports sys and reaches mirror/append code on Linux. Invalid strike conversion rolls back the snapshot insert in `mirror_record`. A competing process holding the real lock causes the logger to skip without data writes. | One SQLite transaction and single-flight locking do not make two filesystem appends atomic or recoverable. |
| F11 projection | Out-of-file-order canonical UTC timestamps select the correct latest row. Missing heatmap cells are null while an explicit zero stays numeric. UTC fixture times render as ET 10:00/10:05. | Offset ordering, formula lineage and actual visual rendering remain open. |

## New and remaining verified failures

### R1 — A single long call creates a false spot-gamma root (new solver failure)

[The exact-zero branch](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/interpreter.py#L449) treats a transition from nonzero gamma to floating-point zero as a root. Fixture: S=K=100, one call, OI=100, sigma=.001, 60 seconds to expiry. Output is `gamma_flip=100.05`, roots `[100.05]`. Analytic Black–Scholes gamma for one long call with positive OI is strictly positive at every finite positive spot. The returned level is underflow, not an inventory sign change.

**Acceptance (F05/T11):** the same one-sided inventory must return no root; include small-IV/near-expiry tails, exact endpoint roots, zero inventory and tangency fixtures. Require stable numerics, declared bracketing/tangency policy, residuals and conditioning diagnostics. Never promote an underflow zero to a root. Preserve a genuinely sign-changing root and report all roots in the declared domain.

### R2 — Averaging leg IV erases two real scenario roots (new solver failure)

[The solver replaces both leg IVs with their average](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/interpreter.py#L425). Fixture: same strike 100, S=100, 60 seconds left, call IV=.1, put IV=.4, OI=100 each. Patch roots are `[]`; the independent per-leg frozen-IV oracle gives **99.9762844236 and 100.0237097916**. Oracle signed net gamma at 99.9/100/100.1 is approximately -13980.67 / +216993.95 / -13979.44 shares per dollar. Averaging makes the two equal-OI legs cancel everywhere.

**Acceptance (F05/T10/T11):** freeze IV per contract/leg, then reconcile roots with an independent per-leg gamma oracle and converged bracketing. If a shared-IV scenario is intended, name it explicitly as a different model, retain the input/model lineage, and do not present its roots as the original chain's frozen-IV roots. State/refine the scan-grid policy; this fixture's roots are closer than the current 0.05-dollar grid step.

### R3 — Process restart never repairs missing strike JSONL (new logger rewrite failure)

[The early return checks only DB and main JSONL](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/maxpain_log.py#L166); [strike history append follows main append](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/maxpain_log.py#L171). Inject an invalid GEX append destination after successful mirror and main append, then restart in a separate process with the same clock/fixture and a valid GEX destination. Counts remain DB snapshots=1, DB strikes=1, main JSONL=1, GEX JSONL absent. Retry prints `already logged`; the heatmap's source stays permanently incomplete.

**Acceptance (F09/F10/T14–T16):** independently reconcile all required projections from one declared authoritative journal. Retry must repair the missing strike record. Crash/restart before/after each DB commit and each append, disk-full/locked DB/truncated tails, then replay twice: identities, canonical values and counts must agree. Preserve real POSIX contention coverage. This run tests a real append failure and actual process restart; it does not claim power-loss/fsync guarantees or every crash point was tested.

### R4 — Conflicting duplicate mirrors create a hybrid record; event retries still duplicate

[`INSERT OR IGNORE` is applied independently to parent and strike rows](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/tape_db.py#L156). First `(ts,expiry)` record has spot=100 and strike 100=.02; second with same key has spot=200, strike 100=2 and new strike 101=3. Persisted state is **spot=100, strikes 100=.02 and 101=3**, with no conflict receipt. This is neither accepted payload. Separately, [logger identity is freshly computed time](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/maxpain_log.py#L70): replaying an identical feed with unchanged source/compute timestamps at logger time +1 second creates two DB snapshots.

**Acceptance (F10/T06/T08/T15/T16):** identical identity+hash is an explicit duplicate; changed payload is an explicit conflict or availability-timed revision, with no partial strike additions. Define source event versus periodic observation identity; a new receipt clock alone must not silently masquerade as idempotent event replay. Replay A,C,B,A across restart with counts/reasons and no hybrid state.

### R5 — Latest timestamp is still wrong across valid offsets

[Sorting compares strings](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/dashboard_build.py#L79). `14:00:00+00:00` spot=100 sorts after `10:05:00-04:00` spot=200, although the second is 14:05 UTC. Output incorrectly selects spot=100. This does not negate the passing canonical-UTC/file-order fix. It is a contract failure for mixed timestamp offsets; this review does not claim current logger output normally uses mixed offsets.

**Acceptance (F11/T04/T08/T16):** normalize aware timestamps to UTC before ordering; preserve original timestamp and timezone. The fixture must choose 200 and order heatmap/range history consistently. Explicitly reject/quarantine naive, invalid and future timestamps; specify ties and late-arrival policy. Test DST folds and equivalent instants.

### R6 — Historical heatmap mixes 100× formula units

[The heatmap consumes unversioned values directly](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/dashboard_build.py#L164), then [infers version from a hardcoded date note](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/dashboard_build.py#L190). Same exposure, v1=200 and v2=2 million, renders `[200,2]` in one matrix. Even explicit fixture `gex_formula` tags are ignored. Logger's strike JSONL contains neither formula version nor units. The reviewed patch is dated October 4 yet the note asserts a universal October 5 cutover.

**Acceptance (F03/F04/F11/T09/T16):** retain formula/units on each strike history event, normalize verified v1 to canonical v2 exactly once or segregate the displays. Unknown versions stay unavailable or separately labeled; do not infer formula from date. Same-exposure fixture must yield `[2,2]` or separately versioned series, preserving raw history. Ensure snapshot, SQLite, strike history and UI/export agree.

### R7 — Provenance and known-at gates remain incorrect

[Rows still get unconditional `rtd`](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/interpreter.py#L357), and [chain metadata inherits quote time/realtime](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/interpreter.py#L396). Synthetic Cboe-delayed rows with their own source timestamp plus a Yahoo quote still produce `src=rtd`, `greeks=observed`, `delay=realtime`, with the quote timestamp as RTD chain `as_of`. A quote dated a day after the frozen decision still returns `status=ok`. Adding metadata fields has not repaired their truth.

**Acceptance (F01/F03/T01/T04):** preserve independent quote/chain/Greek lineage, source and receipt times and observed/modeled state through API/SSE, logger, DB, alerts and UI. Never upgrade a chain from the quote's provider. Unknown source age remains unknown. Freeze skew/availability thresholds, reject future/ambiguous clocks, and show unavailable/stale reasons. Verify the deployed upstream schema/revision separately before live-source claims. No live polling is authorized here.

### R8 — Expected-move horizon copy changes, calculation remains

[Current straddle is scaled again by remaining/session time](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/interpreter.py#L214). With current straddle=2 and 5850 seconds left, `remaining_dollars=1`; note still calls the current-maturity quote a full-session move. The new quoted/modeled tags are helpful, but do not justify this horizon transformation.

**Acceptance (F07/T12):** retain current-maturity quoted straddle as its price proxy. Define and validate any separate expected-move model/horizon using independent repricing/calibration; do not assert that a current quote is an opening/full-session quote. Fixture must either retain 2 or return a separately justified model with lineage, assumptions and validation.

### R9 — Backfill dry-run GEX counts disagree with actual replay

[Dry-run always increments GEX accepted](https://github.com/3pacs/muse/blob/ed3b8741c21b58438be1da65a1dca17d0c5e3bac/tape_db.py#L224). One already-present strike-history line gives dry accepted=1/ignored=0; actual replay accepted=0/ignored=1. Snapshot duplicate counts agree in this fixture. Returned counters are an improvement over the original silent suppression, but are not yet a reliable preview.

**Acceptance (F10/T16):** dry-run and real replay use the same validation, conflict and duplicate policy, distinguishing processed lines, inserted rows and partial duplicates. Compare counts on valid, duplicate, invalid-strike, changed-payload and truncated-line fixtures; retain rejected/conflict reasons. A dry-run must not write.

## Remaining gates and visual work

Stage 0/1 remains provisional: source/availability contract is incomplete. Calendar/early-close/expired-life behavior, coverage and malformed input handling, duplicate option roots/multipliers, last-good stale transport, and quality-gated alerts were not runtime-tested here and are **not retired** by these 21 checks. Static code still uses weekday/clock market checks and a minimum 60-second expiry life; missing values often default to zero. Do not claim those challenge cases passed.

Stage 2 remains blocked by R1–R6/R9 and missing complete crash/replay receipts. Stage 3 has no committed data manifest, frozen splits/baselines, untouched held-out receipt, costs or incremental-value evidence. No alpha result is asserted. Stage 4 activation is outside this review.

Dashboard data projection improved, but the patch contains **no HTML/JS/CSS frontend, screenshots, interaction recording, token sheet or accessibility/performance receipts**. Actual UI polish cannot be judged from JSON. Stage V is **BLOCKED: frontend source/artifact unavailable**, not visually failed. Recover the actual frontend head, then exercise the first challenge's 320/390/768/1440px layouts and synthetic partial/stale/error fixtures, grayscale missing-vs-zero behavior, keyboard/tap/replay interactions, contrast and measured latency. Data and visual acceptance remain separate. The data builder's fixed source/formula notes are not substitutes for dynamic trust badges.

Next bounded assignment: fix **R1** with one minimal solver patch, immutable before/after fixture receipts and an independent numerical oracle, then stop for controller review. Fix remaining items in separate scoped cycles. No stage is accepted by this report; human/controller reviewer receipt remains pending.

## Reproduction and receipt

The appendix is the exact self-contained synthetic harness executed on Dell. Save the Python fence as `review.py`, then run against a clone containing both immutable commits:

```bash
python3 review.py /absolute/path/to/muse results.json
```

The harness invokes `git show` locally; it does not fetch or modify the repository. It exits zero when the harness completes, even when contract assertions fail; inspect `pass_contract`, `passes` and `failures` in `results.json`. Unexpected harness exceptions exit nonzero. Fixtures are defined inline, with no provider data or external dependencies. The machine receipt below lists every check, including failures. No original JSONL/DB journal is rewritten. Git source diff whitespace check passed; there is no project test suite to claim as green.

Session report: what changed—this docs-only handoff; verified—offline source-pinned cases and narrow publication scope; blocked—Stage 1/2 acceptance, frontend visual QA, data/research/deployment evidence; left—scoped fixes and controller receipts. The prescribed `agent-report` executable and Mac report script are unavailable on this Dell local host; a local coordination/report receipt is retained instead. No Obsidian hub delivery is claimed.


### Manifest

```json
{
  "reviewed_head": "ed3b8741c21b58438be1da65a1dca17d0c5e3bac",
  "baseline": "43c2cd41f3823adcda5222d4648131a374c47a59",
  "challenge_head": "16b1d4a4261591811c24b679196360e4182f5caf",
  "harness_sha256": "97061b71e2f34f7a944403158cf2a73215d2e5e1ebe5b5c1bc2a571153ebb81c",
  "results_sha256": "1000fd5a507d7d2b24f1cb1243121a70d07284ac42d687a3bab1624b355e1d4f",
  "python": "3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]",
  "fixture_policy": "inline synthetic, no provider data",
  "transport_policy": "urlopen/socket connect blocked; synthetic fetch; no polling entrypoint",
  "persistence_policy": "disposable directories; actual subprocess restart and POSIX fcntl contention",
  "reviewer_status": "PENDING",
  "generated_utc": "2026-10-04T10:44:54.761155+00:00"
}
```

### Machine receipt

```json
{
  "source_head": "ed3b8741c21b58438be1da65a1dca17d0c5e3bac",
  "baseline": "43c2cd41f3823adcda5222d4648131a374c47a59",
  "python": "3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]",
  "synthetic_only": true,
  "network_blocked": true,
  "results": [
    {
      "name": "gex_units",
      "pass_contract": true,
      "observed": {
        "before": 2.0,
        "after": 0.02
      },
      "expected": ".02 USD million per 1% spot move"
    },
    {
      "name": "source_fidelity",
      "pass_contract": false,
      "observed": {
        "row": {
          "strike": 100.0,
          "src": "rtd",
          "greeks": "observed",
          "net_gex_m": 0.02,
          "call_gex_m": 0.02,
          "put_gex_m": -0.0
        },
        "sources": {
          "rtd": {
            "as_of": "2026-10-05T19:59:00+00:00",
            "delay": "realtime",
            "n_strikes": 1
          },
          "nasdaq": {
            "as_of": null,
            "delay": "~15min",
            "n_strikes": 0,
            "stale": false
          }
        }
      },
      "expected": "retain delayed provider and chain timestamp; never inherit quote realtime"
    },
    {
      "name": "future_time_gate",
      "pass_contract": false,
      "observed": {
        "status": "ok",
        "quote_as_of": "2026-10-06T19:59:00+00:00"
      },
      "expected": "quarantine available/source time after decision"
    },
    {
      "name": "underflow_root",
      "pass_contract": false,
      "observed": {
        "spot": 100.0,
        "expiry": "2026-10-05",
        "gex_formula": "v2",
        "gex_units": "USD millions per 1% spot move",
        "net_gex_m": 0.02,
        "gamma_flip": 100.05,
        "gamma_flip_method": "spot_root_frozen_iv_oi",
        "gamma_flip_roots": [
          100.05
        ],
        "gamma_flip_note": null,
        "call_wall": 100.0,
        "put_wall": null,
        "regime": "positive-gamma (pinning)",
        "by_strike": [
          {
            "strike": 100.0,
            "src": "rtd",
            "greeks": "observed",
            "net_gex_m": 0.02,
            "call_gex_m": 0.02,
            "put_gex_m": -0.0
          }
        ],
        "top_strikes": [
          {
            "strike": 100.0,
            "src": "rtd",
            "greeks": "observed",
            "net_gex_m": 0.02,
            "call_gex_m": 0.02,
            "put_gex_m": -0.0
          }
        ],
        "max_pain": 100.0
      },
      "expected": "no root for single long call with positive OI"
    },
    {
      "name": "leg_iv_roots",
      "pass_contract": false,
      "observed": {
        "output": [],
        "oracle_roots": [
          99.97628442356458,
          100.02370979163823
        ],
        "oracle_signs": [
          -13980.66693279276,
          216993.94716872432,
          -13979.440205613972
        ]
      },
      "expected": "two per-leg frozen-IV roots near 100"
    },
    {
      "name": "charm_oracle",
      "pass_contract": true,
      "observed": {
        "max_absolute_error": 6.629530258095429e-10,
        "baseline_error": 0.042994408439981084
      },
      "expected": "absolute error <1e-7 on these six samples; no full-domain certification"
    },
    {
      "name": "rr_tolerance",
      "pass_contract": true,
      "observed": null,
      "expected": "far deltas .5/-.5 do not become 25-delta RR"
    },
    {
      "name": "activity_names",
      "pass_contract": true,
      "observed": [
        "spot",
        "expiry",
        "pc_volume",
        "pc_oi",
        "call_volume",
        "put_volume",
        "call_oi",
        "put_oi",
        "elevated_volume_activity",
        "top_volume_activity",
        "activity_note"
      ],
      "expected": "unsigned activity keys and explanatory note"
    },
    {
      "name": "straddle_horizon",
      "pass_contract": false,
      "observed": {
        "dollars": 2.0,
        "dollars_kind": "quoted",
        "pct": 2.0,
        "remaining_dollars": 1.0,
        "remaining_kind": "modeled",
        "remaining_pct": 1.0,
        "atm_strike": 100,
        "note": "dollars = quoted ATM straddle mid (market-implied full-session move); remaining = that quote scaled once by sqrt(time left / 6.5h)"
      },
      "expected": "current maturity straddle=2; no unexplained rescaling to 1"
    },
    {
      "name": "cache_ttl",
      "pass_contract": true,
      "observed": [],
      "expected": "expired or previous-date wings discarded on refresh failure"
    },
    {
      "name": "cache_date",
      "pass_contract": true,
      "observed": [],
      "expected": "expired or previous-date wings discarded on refresh failure"
    },
    {
      "name": "gex_append_recovery",
      "pass_contract": false,
      "observed": {
        "counts_DBsnapshot_DBstrike_mainJSONL_GEXfile": [
          1,
          1,
          1,
          0
        ],
        "first": "injected GEX append failure after DB commit + main JSONL append\n",
        "first_error": "",
        "retry": "already logged | ts=2026-10-05T19:59:00+00:00\n",
        "retry_error": ""
      },
      "expected": "retry repairs missing GEX history after DB+main append"
    },
    {
      "name": "posix_lock_contention",
      "pass_contract": true,
      "observed": "another logger run in flight; skipping\n",
      "expected": "contending process skips without data writes"
    },
    {
      "name": "stable_event_identity",
      "pass_contract": false,
      "observed": 2,
      "expected": "same fixed feed updated_at/quote_as_of replayed with new logger clock produces one event identity"
    },
    {
      "name": "mirror_transaction_rollback",
      "pass_contract": true,
      "observed": 0,
      "expected": "invalid strike rolls snapshot insert back"
    },
    {
      "name": "mirror_conflict",
      "pass_contract": false,
      "observed": {
        "snapshot_spot": 100.0,
        "strikes": [
          [
            100.0,
            0.02
          ],
          [
            101.0,
            3.0
          ]
        ]
      },
      "expected": "changed payload for same identity explicitly conflicts, no Frankenstein strike set"
    },
    {
      "name": "backfill_dry_run_counts",
      "pass_contract": false,
      "observed": {
        "dry": {
          "snap_accepted": 0,
          "snap_ignored": 1,
          "snap_rejected": 0,
          "gex_accepted": 1,
          "gex_ignored": 0,
          "gex_rejected": 0
        },
        "actual": {
          "snap_accepted": 0,
          "snap_ignored": 1,
          "snap_rejected": 0,
          "gex_accepted": 0,
          "gex_ignored": 1,
          "gex_rejected": 0
        }
      },
      "expected": "predicted accepted/ignored counts match actual duplicate replay"
    },
    {
      "name": "timestamp_offsets",
      "pass_contract": false,
      "observed": 100,
      "expected": "200 at 14:05Z is later than 100 at 14:00Z"
    },
    {
      "name": "same_offset_ordering",
      "pass_contract": true,
      "observed": 200,
      "expected": "out-of-file-order latest correct with canonical UTC timestamps"
    },
    {
      "name": "heatmap_missing_zero",
      "pass_contract": true,
      "observed": {
        "strikes": [
          100.0,
          101.0
        ],
        "times": [
          "10:00",
          "10:05"
        ],
        "values": [
          [
            null,
            0.0
          ],
          [
            0.0,
            null
          ]
        ],
        "time_zone": "America/New_York"
      },
      "expected": "true zero distinct from missing; ET labels 10:00/10:05"
    },
    {
      "name": "mixed_formula_heatmap",
      "pass_contract": false,
      "observed": {
        "heatmap": {
          "strikes": [
            100.0
          ],
          "times": [
            "10:00",
            "10:05"
          ],
          "values": [
            [
              200.0
            ],
            [
              2.0
            ]
          ],
          "time_zone": "America/New_York"
        },
        "notes": [
          "source mix unknown; Nasdaq wings ~15 min delayed; walls/flip can flicker on mixed snapshots",
          "GEX $m units changed 2026-10-05 (v2 = USD per 1% move, canonical); records before that date are v1 and read 100x larger",
          "GEX/charm/vanna dollar magnitudes swing on feed mixing \u2014 treat levels as signal, dollar sizes as rough",
          "Dealer positioning assumes long calls / short puts (standard GEX convention) \u2014 a prior, not observed truth"
        ]
      },
      "expected": "normalize or segregate v1/v2 with per-record units, not date inference"
    }
  ],
  "passes": 10,
  "failures": 11,
  "harness_sha256": "97061b71e2f34f7a944403158cf2a73215d2e5e1ebe5b5c1bc2a571153ebb81c"
}
```

### Executed harness

```python
"""Offline synthetic Muse review. No application entrypoints or network transport.
Run: python3 review.py ../muse-review results.json
"""
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import pathlib
import socket
import sqlite3
import subprocess
import sys
import tempfile
import types
import urllib.request
from unittest.mock import patch

ROOT = pathlib.Path(sys.argv[1]).resolve()
HEAD = 'ed3b8741c21b58438be1da65a1dca17d0c5e3bac'
BASE = '43c2cd41f3823adcda5222d4648131a374c47a59'
NOW = dt.datetime(2026, 10, 5, 19, 59, tzinfo=dt.timezone.utc)

def blocked(*a, **kw):
    raise AssertionError('unmocked network attempted')
urllib.request.urlopen = blocked
socket.create_connection = blocked
socket.socket.connect = blocked

class Clock(dt.datetime):
    instant = NOW
    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

def load(name, sha=HEAD):
    source = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{sha}:{name}.py'], text=True)
    m = types.ModuleType(name)
    m.__file__ = str(ROOT / (name+'.py'))
    exec(compile(source, m.__file__, 'exec'), m.__dict__)
    if hasattr(m, 'datetime'):
        m.datetime = Clock
    return m

def leg(side='C', iv=.2, oi=100, strike=100, gamma=.02, **kw):
    return dict(expiry='2026-10-05', strike=strike, side=side, iv=iv,
                open_interest=oi, gamma=gamma, volume=600, delta=.5 if side=='C' else -.5,
                bid=1., ask=1., provider='cboe_delayed', as_of='2026-10-05T19:44:00+00:00', **kw)

def snapshot(rows, sha=HEAD, quote_time='2026-10-05T19:59:00+00:00'):
    m=load('interpreter', sha)
    m.fetch_json=lambda url: {'quote': {'price':100, 'as_of':quote_time, 'source':'yahoo'}} if url==m.STATE_URL else {'contracts':rows, 'provider':'cboe_delayed'}
    m.fetch_nasdaq_0dte=lambda now: []
    return m, m.build_snapshot()

def logger_worker(folder, gex_failure):
    folder=pathlib.Path(folder)
    m=load('maxpain_log')
    db=load('tape_db'); sys.modules['tape_db']=db
    db.HIDDEN=str(folder); db.DB_PATH=str(folder/'tape.db')
    m.LOG_PATH=str(folder/'history.jsonl'); m.GEX_SNAP_PATH=str(folder/('bad-directory' if gex_failure else 'gex.jsonl'))
    m.LOCK_PATH=str(folder/'logger.lock'); m.EVENTS_PATH=str(folder/'absent-events.json')
    m.fetch=lambda: {'status':'ok','updated_at':NOW.isoformat(),'quote_as_of':NOW.isoformat(),'expiry':'2026-10-05','spot':100,'gamma':{'by_strike':[{'strike':100,'net_gex_m':.02}], 'gex_formula':'v2'}}
    if gex_failure:
        (folder/'bad-directory').mkdir(exist_ok=True)
    if len(sys.argv)>6:
        Clock.instant=NOW+dt.timedelta(seconds=int(sys.argv[6]))
    try:
        m.main()
    except IsADirectoryError:
        print('injected GEX append failure after DB commit + main JSONL append')

if len(sys.argv)>3 and sys.argv[3]=='worker':
    logger_worker(sys.argv[4], sys.argv[5]=='fail')
    sys.exit(0)

results=[]
def record(name, good, observed, expected):
    results.append(dict(name=name, pass_contract=bool(good), observed=observed, expected=expected))

# Unit before/after receipt; same fixture at both heads.
before=snapshot([leg()],BASE)[1]; m,after=snapshot([leg()])
record('gex_units',after['gamma']['net_gex_m']==.02, {'before':before['gamma']['net_gex_m'],'after':after['gamma']['net_gex_m']},'.02 USD million per 1% spot move')
record('source_fidelity',after['gamma']['by_strike'][0]['src']=='cboe_delayed', {'row':after['gamma']['by_strike'][0], 'sources':after['sources']},'retain delayed provider and chain timestamp; never inherit quote realtime')
future=snapshot([leg()],quote_time='2026-10-06T19:59:00+00:00')[1]
record('future_time_gate',future['status']!='ok',{'status':future['status'],'quote_as_of':future['quote_as_of']},'quarantine available/source time after decision')

# One long call has strictly positive analytic gamma. Floating underflow is not a root.
_,tiny=snapshot([leg(iv=.001)])
record('underflow_root',tiny['gamma']['gamma_flip_roots']==[], tiny['gamma'], 'no root for single long call with positive OI')

# Different call/put IV at same strike: independent per-leg frozen-IV scenario.
_,legs=snapshot([leg(iv=.1),leg('P',iv=.4)])
T=60/(365.25*24*3600)
def oracle_gamma(S,K,sigma):
    d1=(math.log(S/K)+(.043-.013+.5*sigma*sigma)*T)/(sigma*math.sqrt(T))
    return math.exp(-.013*T-.5*d1*d1)/(math.sqrt(2*math.pi)*S*sigma*math.sqrt(T))
def ng(s): return 10000*(oracle_gamma(s,100,.1)-oracle_gamma(s,100,.4))
def bisect(a,b):
    for _ in range(80):
        c=(a+b)/2
        if (ng(a)<0)==(ng(c)<0): a=c
        else: b=c
    return (a+b)/2
roots=[bisect(99.9,100),bisect(100,100.1)]
record('leg_iv_roots',len(legs['gamma']['gamma_flip_roots'])==2, {'output':legs['gamma']['gamma_flip_roots'],'oracle_roots':roots,'oracle_signs':[ng(99.9),ng(100),ng(100.1)]},'two per-leg frozen-IV roots near 100')

# Sample independent delta derivatives, clock-decay sign and year conversion.
def delta(S,K,T,r,q,v,call):
    x=(math.log(S/K)+(r-q+.5*v*v)*T)/(v*math.sqrt(T))
    return math.exp(-q*T)*(.5*math.erfc(-x/math.sqrt(2))-(0 if call else 1))
errs=[]; olderrs=[]
old=load('interpreter',BASE)
for K in (90,100,110):
    for call in (True,False):
        t=.01; eps=1e-7
        expected=-(delta(100,K,t+eps,.043,.013,.2,call)-delta(100,K,t-eps,.043,.013,.2,call))/(2*eps)
        errs.append(abs(m.charm(100,K,t,.043,.013,.2,call)-expected))
        olderrs.append(abs(old.charm(100,K,t,.043,.013,.2,call)-expected))
record('charm_oracle',max(errs)<1e-7, {'max_absolute_error':max(errs),'baseline_error':max(olderrs)},'absolute error <1e-7 on these six samples; no full-domain certification')
record('rr_tolerance',after['iv']['risk_reversal_25d'] is None,after['iv']['risk_reversal_25d'],'far deltas .5/-.5 do not become 25-delta RR')
record('activity_names','top_volume_activity' in after['flow'] and 'top_flow' not in after['flow'],list(after['flow']),'unsigned activity keys and explanatory note')
position=m.compute_positioning({100:{'call':{'bid':1,'ask':1},'put':{'bid':1,'ask':1}}},[100],100,5850)
record('straddle_horizon',position['expected_move']['remaining_dollars']==2,position['expected_move'],'current maturity straddle=2; no unexplained rescaling to 1')

# Cache expiry and date boundary with urlopen blocked; deliberate fetch failure.
for age,label,name in ((1801,'Oct 5','cache_ttl'),(1,'Oct 4','cache_date')):
    cache=load('interpreter'); cache._NQ.update(at=10000-age,as_of='old',label=label,rows=[{'strike':100}],stale=False)
    with patch.object(cache.time,'time',return_value=10000):
        got=cache.fetch_nasdaq_0dte(NOW)
    record(name,got==[],got,'expired or previous-date wings discarded on refresh failure')

# Real POSIX fcntl, actual child process restart, only disposable paths.
with tempfile.TemporaryDirectory() as td:
    args=[sys.executable,str(pathlib.Path(__file__).resolve()),str(ROOT),'unused','worker',td]
    # Separate processes; fixed clock reproduces retry of same identity.
    a=subprocess.run(args+['fail'],text=True,capture_output=True)
    b=subprocess.run(args+['ok'],text=True,capture_output=True)
    con=sqlite3.connect(pathlib.Path(td)/'tape.db')
    counts=[con.execute('select count(*) from snapshots').fetchone()[0],con.execute('select count(*) from gex_strikes').fetchone()[0],len((pathlib.Path(td)/'history.jsonl').read_text().splitlines()),int((pathlib.Path(td)/'gex.jsonl').exists())]
    record('gex_append_recovery',counts==[1,1,1,1],{'counts_DBsnapshot_DBstrike_mainJSONL_GEXfile':counts,'first':a.stdout,'first_error':a.stderr,'retry':b.stdout,'retry_error':b.stderr},'retry repairs missing GEX history after DB+main append')
    con.close()

with tempfile.TemporaryDirectory() as td:
    args=[sys.executable,str(pathlib.Path(__file__).resolve()),str(ROOT),'unused','worker',td]
    with open(pathlib.Path(td)/'logger.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        held=subprocess.run(args+['ok'],text=True,capture_output=True)
        record('posix_lock_contention','another logger run in flight' in held.stdout and not (pathlib.Path(td)/'tape.db').exists(),held.stdout,'contending process skips without data writes')
    subprocess.run(args+['ok'],text=True,capture_output=True,check=True)
    subprocess.run(args+['ok','1'],text=True,capture_output=True,check=True)
    with sqlite3.connect(pathlib.Path(td)/'tape.db') as con:
        n=con.execute('select count(*) from snapshots').fetchone()[0]
    record('stable_event_identity',n==1,n,'same fixed feed updated_at/quote_as_of replayed with new logger clock produces one event identity')

with tempfile.TemporaryDirectory() as td:
    db=load('tape_db'); db.HIDDEN=td; db.DB_PATH=str(pathlib.Path(td)/'tape.db'); con=db.connect();db.init_db(con)
    rec={'ts':NOW.isoformat(),'expiry':'2026-10-05','spot':100,'gex_formula':'v2'}
    try: db.mirror_record(rec,{'bad-strike':.02},con)
    except ValueError: pass
    n=con.execute('select count(*) from snapshots').fetchone()[0]
    record('mirror_transaction_rollback',n==0,n,'invalid strike rolls snapshot insert back')
    db.mirror_record(rec,{'100.0':.02},con)
    db.mirror_record(dict(rec,spot=200),{'100.0':2,'101.0':3},con)
    strikes=[tuple(x) for x in con.execute('select strike,net_gex_m from gex_strikes order by strike')]
    record('mirror_conflict',len(strikes)==1,{'snapshot_spot':con.execute('select spot from snapshots').fetchone()[0],'strikes':strikes},'changed payload for same identity explicitly conflicts, no Frankenstein strike set')
    db.LOG_PATH=str(pathlib.Path(td)/'main.jsonl');db.GEX_PATH=str(pathlib.Path(td)/'gex.jsonl')
    pathlib.Path(db.LOG_PATH).write_text(json.dumps(rec)+'\n')
    pathlib.Path(db.GEX_PATH).write_text(json.dumps({'ts':rec['ts'],'expiry':rec['expiry'],'gex_m':{'100.0':.02}})+'\n')
    dry=db.backfill(con,dry_run=True); real=db.backfill(con)
    record('backfill_dry_run_counts',dry==real,{'dry':dry,'actual':real},'predicted accepted/ignored counts match actual duplicate replay')
    con.close()

def dashboard(recs,snaps):
    with tempfile.TemporaryDirectory() as td:
        db=load('dashboard_build');db.OUT_PATH=str(pathlib.Path(td)/'dashboard.json')
        db.load_jsonl=lambda p: recs if p==db.LOG_PATH else snaps
        with patch.object(sys,'argv',['dashboard_build.py','2026-10-05','--force']),contextlib.redirect_stdout(io.StringIO()):db.main()
        return json.loads(pathlib.Path(db.OUT_PATH).read_text())

recs=[{'expiry':'2026-10-05','ts':'2026-10-05T14:00:00+00:00','spot':100},{'expiry':'2026-10-05','ts':'2026-10-05T10:05:00-04:00','spot':200}]
out=dashboard(recs,[])
record('timestamp_offsets',out['latest']['spot']==200,out['latest']['spot'],'200 at 14:05Z is later than 100 at 14:00Z')
recs=[{'expiry':'2026-10-05','ts':'2026-10-05T14:05:00+00:00','spot':200},{'expiry':'2026-10-05','ts':'2026-10-05T14:00:00+00:00','spot':100}]
out=dashboard(recs,[{'expiry':'2026-10-05','ts':r['ts'],'gex_m':{'100.0':0.0} if i==0 else {'101.0':.02}} for i,r in enumerate(recs)])
record('same_offset_ordering',out['latest']['spot']==200,out['latest']['spot'],'out-of-file-order latest correct with canonical UTC timestamps')
record('heatmap_missing_zero',out['heatmap']['values']==[[None,0.0],[0.0,None]],out['heatmap'],'true zero distinct from missing; ET labels 10:00/10:05')
mixed=dashboard(recs,[{'expiry':'2026-10-05','ts':'2026-10-05T14:00:00+00:00','gex_m':{'100.0':200.0},'gex_formula':'v1'},{'expiry':'2026-10-05','ts':'2026-10-05T14:05:00+00:00','gex_m':{'100.0':2.0},'gex_formula':'v2'}])
record('mixed_formula_heatmap',mixed['heatmap']['values']==[[2.0],[2.0]],{'heatmap':mixed['heatmap'],'notes':mixed['data_quality']},'normalize or segregate v1/v2 with per-record units, not date inference')

output={'source_head':HEAD,'baseline':BASE,'python':sys.version,'synthetic_only':True,'network_blocked':True,'results':results,'passes':sum(r['pass_contract'] for r in results),'failures':sum(not r['pass_contract'] for r in results),'harness_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
pathlib.Path(sys.argv[2]).write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
```
