# ROUND PROTOCOL — you are ONE round of this repo's self-evolution loop

Fresh context; your only memory is the disk. Supervisor contract:
- env `ROUND_N` = this round's number (R-space; new experiments get E# = max(existing)+1).
- env `ROUND_DEADLINE_EPOCH` = hard kill time. Check `date +%s` NOW. Stop starting new work
  at T-15min; RECORD must be committed by T-5min. If these vars are unset you are being
  driven interactively: assume no deadline, but follow every other rule.
- You owe back, ALL on disk before the deadline: ≥1 commit, STATUS.md overwritten, ≥1 ledger
  row (or an experiments row saying why none), `./loop/check.sh` green.
- NEVER-KILL-INFRA (Invariant 8). Never double-drive: preflight fails if the lock is held.

## 0. BOOTSTRAP (execute, don't trust prose)
Run `./loop/preflight.sh`.
- It fails on `loop/.state/quarantine` → the previous round failed post-checks: read the
  file, fix the breach, clear it. That is this round's FIRST job.
- The smoke check fails → fixing the wake IS this round's job, nothing else.

## 1. ORIENT (cold read, fixed order — AGENTS.md §COLD START; ~4k tokens)
STATUS.md → loop/ledger/BOARD.md → docs/LESSONS.md → `git log --oneline -12` +
`git log -3 --format=%B` → loop/.state/inflight.json.
Mandatory adoption, BEFORE any new work:
a. inflight.json non-empty → adopt or close that run (read its log, write its ledger row,
   clear the file). Uncommitted WIP in the tree → finish and commit it end-to-end first.
b. Adjudicate every `provisional` ledger row from prior rounds: append a `confirmed` row
   (red-team survived + still reproducible) or a `refuted`/`superseded` row with
   `supersedes:` pointing back. check.sh fails on provisionals >2 rounds old.
c. Promotion to docs/DECISIONS.md ([RULING]) happens HERE, next-round — never in the round
   that formed the conclusion. Spine-semantics rulings queue as a CEO gate instead.

## 2. PLAN (one substantial chunk, decided by YOU)
- Take STATUS `next:` #1 — authoritative over GOAL text, over this file, over any memory.
- `grep -i <idea> loop/ledger/experiments.jsonl` FIRST — never re-run a refuted idea unless
  its `do_not_retry_unless` condition has changed.
- Touching a subsystem? Read docs/wiring/<name>.md BEFORE mining source; mine only what the
  card lacks; bank what you mine back into the card (§5b).
- Bundle related work; no micro-rounds. Torn between directions? Generate 3 options, attack
  each (real frontier? fits the deadline? advances the North Star?), pick one, go. NEVER
  pause to ask "continue?" — CEO gates are the only stop.
- Bar already met? It was a floor: raise it toward docs/ARCHITECTURE.md's ladder and the
  LESSONS `## Frontier` section; write the new bar into STATUS `frontier:`.

## 3. BUILD (TDD)
Read docs/rules/standards.md. Red → green → refactor. Small WIP commits are ALLOWED and
encouraged (only the final RECORD commit is gated by check.sh). Never touch the spine paths
enumerated in loop/check.sh (CEO gate). Non-obvious bug → docs/rules/debugging.md Hypothesis
Loop in DEBUG.md; same failure twice → a tricky-bugs case before retrying differently.

## 4. REAL-VERIFY (the only acceptance that counts)
- Read docs/rules/sim-safety.md BEFORE any sim; docs/verify.md for the verdict contract and
  the canonical harness commands (tools/acceptance/).
- Commit a WIP floor BEFORE any long verify. Verify in the FOREGROUND if it fits the
  deadline; else: WIP commit + write loop/.state/inflight.json + STATUS note + end the round
  cleanly. Never end a round waiting on an in-context wakeup — the next round adopts the run.
- Acceptance face = bare `vector-cli` REPL + NL, eyes on frames. Evidence (frames, verdict
  JSON, trimmed log) → var/evidence/R$ROUND_N/ (never /tmp). LOOK at the frames. If the
  vision judge (VECTOR_JUDGE_*) is unset the harness must fail LOUDLY — never a silent pass;
  record the eyes mode honestly: vlm-judge | self-read | human.
- BANK IMMEDIATELY (before any prose, so a kill cannot lose the result): append the
  acceptance.jsonl / experiments.jsonl row, status="provisional". Refuted, failed and plateau
  outcomes get rows with the same care as wins — they prevent re-exploration.
- Red-team every headline claim per docs/rules/red-team.md; record attack + outcome in the
  row's `redteam` field. A claim that fails red-team is a FINDING (refuted row), not a
  failure of the round.

## 5. RECORD (≤15 min; do this even if the work is partial)
a. Ledger rows: banked in §4; add any missing experiments row — every round logs ≥1 E# row
   (type: build|verify|research|debug|review · result · status).
b. Promote, don't duplicate:
   - refuted path / hazard / recipe → ONE line in docs/LESSONS.md ending with E#/D#/hash;
   - symptom-pointed-away bug → docs/tricky-bugs.md case + a regression TEST;
   - wiring you had to mine → overwrite docs/wiring/<name>.md (≤60L, refresh anchors +
     verified-against) in this same commit;
   - a durable ruling (invariant/contract/spine semantic, or a CEO call) → docs/DECISIONS.md
     [RULING] — RARE, and only via §1c next-round promotion.
c. Overwrite STATUS.md (≤40L, fixed fields per docs/rules/doc-governance.md; result ≤3
   lines — the story lives in the commit body; refresh `next:` 1-3; queue gates under
   `gates:` per docs/rules/gates.md).
d. Run `./loop/check.sh` — fix everything it blocks on. The supervisor re-runs it after you
   exit and CI runs it too: you cannot outrun it, so satisfy it now.
e. `git commit` — subject = one-line round summary with R#/E#, verdicts, Ns; body = the full
   round narrative (what worked, what did NOT, why). This commit is the ONLY narrative copy.
   Never push unless the owner said so.

## 6. Gates & stops
CEO gate hit → ≤10-line summary into STATUS `gates:` (format: docs/rules/gates.md), pivot to
non-gated work, never cross. Genuinely nothing non-gated left AND the frontier is exhausted
after a real research round → final experiments row + STATUS `phase: blocked`, stop cleanly.
Every 10th round the supervisor feeds loop/REVIEW.md instead of this file — follow it.
