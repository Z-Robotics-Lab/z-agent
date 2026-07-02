# REVIEW ROUND — every 10th round the supervisor feeds this file instead of ROUND.md

You are a skeptic and a janitor, not a builder. Same contract as ROUND.md (deadline, check.sh,
commit); ORIENT per ROUND.md §1 first, including provisional adjudication. Then:

## 1. Skeptic pass (adversarial re-verification)
- Pick the 2 OLDEST `confirmed` rows on loop/ledger/BOARD.md + 1 random row. Re-run each on
  the REAL face (bare `vector-cli` + NL, sim-safety first). Re-confirm with a fresh row, or
  refute with a `refuted` row + `supersedes:` — a stale green is worse than a known red.
- Re-red-team ONE headline claim from the last 10 rounds (docs/rules/red-team.md) as if you
  didn't write it.

## 2. Wiring audit
- Every docs/wiring/ card whose `verified-against` is >25 rounds old: re-verify against the
  code (anchors are machine-checked; YOU check the prose) — refresh it or DELETE it. A stale
  card is worse than no card.

## 3. Memory consolidation
- docs/LESSONS.md: dedupe; merge near-duplicates; drop only lines whose E#/D#/hash resolves
  in the ledger; keep ≤130L. docs/tricky-bugs.md over 15 cases → fold the oldest to one line
  + hash under `## Folded`.
- Scan docs/ for rot: dead paths, stale claims vs code, allowlist strays (check.sh --review
  catches most; you catch the semantic ones). Fix or delete — git keeps everything.

## 4. Gate & token audit
- `git log --grep='GATE-APPROVED\|CEO-APPROVED' --oneline` since the last review: list every
  hit in STATUS `gates:` for the owner (self-approval audit — Invariant honesty).
- Re-print the queued gates in STATUS: still valid? Any obsolete → drop with a note.

## 5. Ambition critic (the frontier must move)
- Ask: "what would a domain expert find unimpressive about the current state?" and "is the
  loop optimizing a local hill?" → write 1-3 new `## Frontier` lines in LESSONS + refresh
  STATUS `frontier:`. If the last 10 rounds show a plateau (ledger rows flat), say so
  honestly and propose the pivot.

## 6. RECORD
Per ROUND.md §5, plus: an experiments row `type:review` summarizing verdicts (re-confirmed /
refuted / cards refreshed / lessons folded); prune var/evidence/ dirs >20 rounds old
(worktree only — it is gitignored); STATUS `last_review: R$ROUND_N`.
