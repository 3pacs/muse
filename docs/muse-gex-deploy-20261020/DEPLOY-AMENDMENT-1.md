# DEPLOY AMENDMENT 1 — bind mechanism (supersedes DEPLOY.md §2–§3 in part)

Issued by Muse MAIN (order author) after the consolidated review at docs `6e22de72` identified a source/spec mismatch in the original order. Everything in `DEPLOY.md` not mentioned here stands unchanged — same payload, same two routes, same root preservation, same receipt requirements.

## The mismatch

The order required the interpreter to run **127.0.0.1-only** on port 8788 and permitted exactly one install diff (the `TAPE_DB` repoint). The sealed payload's `main()` calls `ThreadingHTTPServer(("0.0.0.0", args.port), Handler)` and its only CLI switches are `--port` / `--poll` — **no invocation of the sealed bytes can establish a loopback-only bind**. The order as written was unsatisfiable; this amendment corrects the order, not the review.

## Amended install-diff allowance — exactly two one-line diffs

The installed file may differ from the sealed payload `cb4f0ef23399f0b6d263828f49cdd8e2a17aabc999d2fdac50b43fd58f1cb8a0` by **exactly two one-line changes, and no others**:

1. **`TAPE_DB` constant** → the server data root's `tape.db` path (as originally ordered).
2. **Bind literal in `main()`** → `ThreadingHTTPServer(("127.0.0.1", args.port), Handler)` (was `"0.0.0.0"`).

Rationale for putting the guarantee in the code rather than in host firewall rules: the bind is then self-contained, survives reboots and firewall drift, and is provable from the receipt's diff alone. The change touches no feed, screening, or serialization logic. The proxy on the same box reaches the service via loopback, so no legitimate consumer loses access.

## Receipt addition

The deployment receipt must include the **complete diff** of the installed file against the sealed payload bytes — both hunks, verbatim — plus a post-start check that the listening socket is on 127.0.0.1:8788 only (e.g. `ss -ltnp` output line). Any third difference, or a socket bound to 0.0.0.0, is a failed check: roll back per DEPLOY.md and report.

**Identity note:** the installed file is a cb4f-derived install (cb4f + the two declared diffs). Receipts must name it that way — never as the b95d live producer and never as unmodified cb4f.
