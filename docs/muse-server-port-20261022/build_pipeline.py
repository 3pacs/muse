#!/usr/bin/env python3
"""Port the exported Muse 0DTE production pipeline (3pacs/muse, branch implementation/0dte-source-20261015,
implementation/pipeline/) to grid-svr paths. Writes out/pipeline/.

Porting changes (the handoff's own list, docs/0DTE-SELF-HOST-HANDOFF.md "Porting changes"):
  * every Muse-VM path -> /data/agent-home/anikdang/muse-0dte-data (data) or /data/agent-home/anikdang/muse-0dte (code)
  * feed URL localhost:8787 -> 127.0.0.1:8788 (8787 on grid-svr is an unrelated dashboard; the 2026-10-20 order says 8788)
  * interpreter: inputs from the gex-watch loopback (127.0.0.1:8769), legacy quote mapped from the gex-screen/2 state,
    bind 127.0.0.1, default port 8788; `sources.quote` labels which quote fed the snapshot.
Nothing else changes. Fails if any anchor is not matched exactly once or any VM path survives.
"""
import hashlib, pathlib, subprocess

HERE = pathlib.Path(__file__).resolve().parent
MUSE = pathlib.Path('/home/anik/dev/muse')
BRANCH = 'origin/implementation/0dte-source-20261015'
PREFIX = 'implementation/pipeline/'
OUT = HERE / 'out' / 'pipeline'
DATA = '/data/agent-home/anikdang/muse-0dte-data'
CODE = '/data/agent-home/anikdang/muse-0dte'


def git(*args):
    return subprocess.run(['git', '-C', str(MUSE), *args], check=True, capture_output=True).stdout


def once(text, a, b, name):
    if text.count(a) != 1:
        raise SystemExit('%s: anchor count %d: %r' % (name, text.count(a), a[:80]))
    return text.replace(a, b)


files = [l for l in git('ls-tree', '-r', '--name-only', BRANCH, '--', PREFIX).decode().split('\n') if l]
assert files, 'no pipeline files found'
OUT.mkdir(parents=True, exist_ok=True)
for path in files:
    rel = path[len(PREFIX):]
    target = OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if rel == 'interpreter.py':
        # The 2026-10-20 deploy order's payload: rev4 sealed, PUBLIC-SAFE variant (no exception text on public error
        # payloads, typed-screened signal detail, non-finite rejected, allow_nan=False). Newer than the Oct-15 intake copy.
        data = git('show', 'pr2:docs/muse-gex-deploy-20261020/interpreter.py')
        assert hashlib.sha256(data).hexdigest().startswith('cb4f0ef2'), 'unexpected interpreter base (want rev4 cb4f0ef2)'
    else:
        data = git('show', '%s:%s' % (BRANCH, path))
    if rel.endswith(('.py', '.sh')):
        text = data.decode('utf-8')
        if rel == 'interpreter.py':
            text = once(text, 'TAPE_DB = ("/home/hatch/workspace/goals/0dte-tape-alert-watch/"\n           "hidden_files/tape.db")',
                        'TAPE_DB = "%s/tape.db"' % DATA, rel)
            text = once(text, 'STATE_URL = "http://gex.stepdad.finance/api/state"', 'STATE_URL = "http://127.0.0.1:8769/api/state"', rel)
            text = once(text, 'CONTRACTS_URL = "http://gex.stepdad.finance/api/contracts"', 'CONTRACTS_URL = "http://127.0.0.1:8769/api/contracts"', rel)
            text = once(text, '\ndef build_snapshot():\n', '''
def legacy_quote(state):
    """Server port (2026-10-22): map the collector's state to the legacy {price, as_of} quote.

    Legacy `quote` first (old server), else the gex-screen/2 frame: the live RTD receipt when present, else the
    public price context. The second return value is recorded under sources.quote so the snapshot says which clock
    it used; a public fallback is never labelled realtime.
    """
    q = state.get("quote")
    if isinstance(q, dict) and q.get("price"):
        return {"price": q.get("price"), "as_of": q.get("as_of")}, {"source": "rtd", "delay": "realtime", "as_of": q.get("as_of")}

    def iso(t):
        try:
            return datetime.fromtimestamp(float(t), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    bq = state.get("brokerage_quote") or {}
    if bq.get("status") == "receipt-only" and bq.get("price"):
        t = iso(bq.get("callback_received_at"))
        return {"price": bq["price"], "as_of": t}, {"source": "rtd", "delay": "realtime", "as_of": t, "clock": "collector-receipt"}
    pp = state.get("public_price") or {}
    if pp.get("values_available") and pp.get("price"):
        t = iso(pp.get("source_time"))
        return {"price": pp["price"], "as_of": t}, {"source": "public_price", "delay": "latency-unverified", "as_of": t, "clock": "provider-as-of"}
    return {"price": 0, "as_of": None}, {"source": None, "delay": None, "as_of": None}


def build_snapshot():
''', rel)
            text = once(text,
                '    quote = state.get("quote", {}) or {}\n    spot = float(quote.get("price") or 0)\n    quote_as_of = quote.get("as_of")\n',
                '    quote, quote_src = legacy_quote(state)  # server port: gex-screen/2 or legacy state\n    spot = float(quote.get("price") or 0)\n    quote_as_of = quote.get("as_of")\n', rel)
            text = once(text,
                '        chain_provider: chain_src,\n        "nasdaq": {',
                '        chain_provider: chain_src,\n        "quote": quote_src,\n        "nasdaq": {', rel)
            # Python 3.10 on grid-svr: nested double quotes inside an f-string expression are 3.12+ syntax (PEP 701).
            nested = '{"-" if gex < 0 else ""}'
            if text.count(nested) != 2:
                raise SystemExit('%s: expected 2 nested-quote f-string expressions, found %d' % (rel, text.count(nested)))
            text = text.replace(nested, "{'-' if gex < 0 else ''}")
            text = once(text, 'srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)', 'srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)', rel)
            text = once(text, 'ap.add_argument("--port", type=int, default=8787)', 'ap.add_argument("--port", type=int, default=8788)', rel)
        if rel == 'run_interpreter.sh':
            text = once(text, 'PORT="${INTERPRETER_PORT:-8787}"', 'PORT="${INTERPRETER_PORT:-8788}"', rel)
        text = text.replace('/home/hatch/workspace/goals/0dte-tape-alert-watch/hidden_files', DATA)
        text = text.replace('~/workspace/goals/0dte-tape-alert-watch/hidden_files', DATA)
        text = text.replace('~/workspace/stepdad-0dte/market_events.json', CODE + '/market_events.json')
        text = text.replace('http://localhost:8787/feed/all', 'http://127.0.0.1:8788/feed/all')
        for bad in ('hatch', '/workspace/', 'localhost:8787', '0.0.0.0'):
            if bad in text and not (bad == '0.0.0.0' and rel != 'interpreter.py'):
                lines = [i + 1 for i, l in enumerate(text.split('\n')) if bad in l]
                raise SystemExit('%s still contains %r at lines %s' % (rel, bad, lines[:5]))
        data = text.encode('utf-8')
    target.write_bytes(data)
    if rel.endswith('.sh'):
        target.chmod(0o755)

for p in sorted(OUT.rglob('*')):
    if p.is_file():
        print(hashlib.sha256(p.read_bytes()).hexdigest()[:16], p.relative_to(OUT))
print('pipeline port ok: %d files' % len(files))
