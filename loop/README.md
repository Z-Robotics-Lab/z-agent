# loop/ — this repo develops itself. Here is how to run that loop.

Any developer + any agent CLI + any LLM can drive it. The protocol is disk files, not a
vendor feature: a supervisor feeds `GOAL.md + ROUND.md` to a fresh-context agent once per
round (`ROUND_KIND=review` every 10th — ROUND.md §7); all memory between rounds lives in
git + the files named in AGENTS.md §State files. Crash-safe by construction: everything
durable is committed before a round ends, so a killed round loses minutes, not work.

## Quick start (hour one)
```bash
cp .env.example loop/local.env      # fill ONE provider block + keys (gitignored)
./loop/preflight.sh                 # env sanity, locks, ledger schema, smoke pointer
./loop/run.sh loop/harness/claude.sh    # Claude Code as the round agent
# or: ./loop/run.sh loop/harness/custom.example.sh   # adapt 5 lines to any agent CLI
```
Watch: `git log --oneline` (one commit per round), STATUS.md, loop/ledger/BOARD.md.

## The supervisor ↔ round contract
- Supervisor (run.sh): per-repo lock (never two loops on one repo) · bumps
  loop/.state/round_n · exports ROUND_N + ROUND_DEADLINE_EPOCH + ROUND_KIND · pipes the
  prompt · after each round: scripts/sim-teardown + loop/check.sh --post (failure
  quarantines the tree — next round fixes the breach first) + heartbeat.
- Round agent: obeys AGENTS.md (constitution) + loop/ROUND.md (per-round protocol); owes
  back ≥1 commit, an overwritten STATUS.md, ≥1 ledger row, a green check.sh.
- Adapter (loop/harness/*.sh): 5 lines. stdin = the round prompt; run your agent CLI
  non-interactive full-auto; exit when the round ends. That is the whole integration.

## Honesty disclosures (read before trusting a long unattended run)
- Full-auto = permissions bypassed: run in a container/VM or a machine you can rebuild.
- Weaker models degrade AMBITION, not SAFETY (check.sh still blocks) — but
  plausible-but-lazy output is not caught; review rounds + the owner backstop quality,
  docs/RULES.md red-team backstops self-deception.
- Gate tokens are tamper-EVIDENT, not tamper-proof (docs/RULES.md CEO-gates).
- Manual driving (no supervisor) loses ROUND_N/deadline/post-checks; CI + preflight still
  gate you; ROUND.md detects interactive mode.
- Sim discipline is NOT optional: docs/RULES.md sim-safety before any sim — one sim at a
  time, tear down via `scripts/sim-teardown`, never `pkill mujoco`, never kill the
  supervisor (Invariant 8).

## Files
- GOAL.md — standing direction (never tasks)
- ROUND.md — the round protocol; §7 = review round (ROUND_KIND=review)
- run.sh — supervisor · preflight.sh — executable ORIENT step 0
- check.sh — THE doc/ledger gate · board.py — BOARD generator
- checks_*.py — schema+anchor validators · checks_allowlist.txt
- ledger/{acceptance,experiments}.jsonl + BOARD.md · harness/ — adapters
- MANIFEST.sha256 — gated-file hashes (regen only in a `CEO-APPROVED:` commit)
- .state/ — gitignored: lock, round_n, heartbeat, quarantine, inflight.json

Multi-day hardening (systemd, watchdog, memory caps) is host-specific — see run.sh header.
