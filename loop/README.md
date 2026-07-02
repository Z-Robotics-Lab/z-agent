# loop/ — this repo develops itself. Here is how to run that loop.

Any developer + any agent CLI + any LLM can drive it. The protocol is disk files, not a
vendor feature: a supervisor feeds `GOAL.md + ROUND.md` (every 10th round: `REVIEW.md`) to an
agent process with a fresh context, once per round; all memory between rounds lives in git +
the files named in AGENTS.md §State files. Rounds are crash-safe by construction: everything
durable is committed before a round ends, so a killed round loses minutes, not work.

## Quick start (hour one)
```bash
cp .env.example loop/local.env      # fill ONE provider block + keys (gitignored)
./loop/preflight.sh                 # env sanity, locks, ledger schema, smoke pointer
./loop/run.sh loop/harness/claude.sh    # Claude Code as the round agent
# or: ./loop/run.sh loop/harness/custom.example.sh   # adapt 5 lines to any agent CLI
```
Watch progress: `git log --oneline` (one commit per round, subject = round summary),
`STATUS.md` (live snapshot), `loop/ledger/BOARD.md` (what is accepted/refuted, on which face).

## The supervisor ↔ round contract
- Supervisor (`run.sh`): holds the per-repo lock (never two loops on one repo), increments
  `loop/.state/round_n`, exports `ROUND_N` + `ROUND_DEADLINE_EPOCH`, pipes the prompt to your
  adapter, and AFTER each round runs `scripts/sim-teardown` + `loop/check.sh --post`
  (failures quarantine the tree — the next round must fix the breach first) + heartbeat.
- Round agent: obeys `AGENTS.md` (constitution) + `loop/ROUND.md` (the per-round protocol).
  It owes back ≥1 commit, an overwritten STATUS.md, ≥1 ledger row, and a green check.sh.
- Adapter (`loop/harness/*.sh`): 5 lines. stdin = the round prompt; run your agent CLI in
  non-interactive full-auto mode; exit when the round ends. That is the whole integration.

## Honesty disclosures (read before trusting a long unattended run)
- Full-auto mode means the agent runs with permissions bypassed — run in a container/VM or
  on a machine you can afford to rebuild if your agent CLI has no sandbox.
- Validated with frontier-class models driving the rounds. A weaker model degrades AMBITION
  (smaller, safer rounds), not SAFETY (check.sh still blocks) — but note: malformed output
  is caught loudly; plausible-but-lazy output is not. Review rounds + the owner are the
  backstop for quality, and `docs/rules/red-team.md` is the backstop for self-deception.
- All gate tokens are tamper-EVIDENT, not tamper-proof (docs/rules/gates.md).
- Driving rounds manually (interactive session, no supervisor)? You lose ROUND_N/deadline/
  post-checks; CI + preflight still gate you. Follow ROUND.md; it detects interactive mode.
- Sim discipline is NOT optional: docs/rules/sim-safety.md before any sim run — one sim at a
  time, tear down via `scripts/sim-teardown`, never `pkill mujoco`, never kill the
  supervisor (Invariant 8).

## Files here
GOAL.md standing direction (never tasks) · ROUND.md round protocol · REVIEW.md every-10th ·
run.sh supervisor · preflight.sh executable ORIENT step 0 · check.sh THE doc/ledger gate ·
board.py BOARD generator · checks_*.py schema+anchor validators · checks_allowlist.txt ·
ledger/{acceptance,experiments}.jsonl + BOARD.md · harness/ adapters ·
MANIFEST.sha256 (gated-file hashes; regen only in a `CEO-APPROVED:` commit) ·
.state/ (gitignored: lock, round_n, heartbeat, quarantine, inflight.json).

Hardening for multi-day unattended runs (systemd restart-always, memory caps, watchdog) is
host-specific — see the comments at the top of run.sh; the loop itself needs none of it to
be correct, only to be immortal.
