# Doc governance — the bounded doc set + who may write what (pull when touching docs)

Law, not advice: `loop/check.sh` BLOCKS violations (agent at RECORD, supervisor post-round, CI).
This card is the human copy; the script's constants are the authority. Git is the archive —
superseded prose is deleted or folded to a stub, never moved to an archive/ directory.

## Allowlist (the only committed .md homes; full list = loop/checks_allowlist.txt)
- Root: AGENTS.md (constitution) · CLAUDE.md (shim) · README.md · STATUS.md · DEBUG.md.
- docs/: ARCHITECTURE, DECISIONS, decisions-index (generated), LESSONS, verify,
  cli-tool-system, skill-protocol, tricky-bugs + rules/*.md (6 cards) + wiring/*.md (≤8 cards).
- loop/: README, GOAL, ROUND, REVIEW + ledger/BOARD.md (generated).
- NEVER create: progress.md (intentionally replaced by STATUS.md + loop/ledger/), ROUNDS.md,
  FRONTIER.md, index/START_HERE/dated-session/manifest docs, nested AGENTS.md.

## Write disciplines (one lifecycle per file — never mix, never duplicate a narrative)
- STATUS.md — snapshot, OVERWRITE every round, ≤40L. Fields: updated / goal(1L) / phase
  (spec|red|green|refactor|review|blocked) / last-round: R# + ≤3L result / frontier(1L) /
  blocked / next: 1-3 items (AUTHORITATIVE task pointer) / gates: queue / last_review: R#.
- Commit message — THE round narrative, written once (subject = R#/E# + verdicts + Ns;
  body = what worked, what did NOT, why). Other files POINT here, never restate.
- loop/ledger/*.jsonl — append-only machine rows (schema in loop/ROUND.md §4/§5);
  BOARD.md regenerated only by loop/board.py.
- docs/DECISIONS.md — RULINGS only, append-only, [RULING] tag required. Admission test: the
  entry changes an invariant, contract, or spine semantic, or records a CEO ruling.
  Everything else = ledger row + commit message. Corrections = new entry + forward link;
  NEVER rewrite/renumber an accepted entry. Overflow (>48 entries) = CEO-gated fold of the
  oldest superseded ruling to a `D### <headline> → git <hash>` stub.
- docs/LESSONS.md — one line per lesson, ends with E#/D#/commit; RA appends, review rounds
  consolidate; a line may drop only if its pointer resolves in the ledger.
- docs/wiring/*.md — overwritten IN THE SAME COMMIT that changes that subsystem's wiring;
  stale cards are deleted, not kept.

## Size caps (hard; enforced by check.sh — the numbers live there)
AGENTS 130L · STATUS 40L · LESSONS 150L · ROUND 120L · GOAL 15L · REVIEW 60L · verify 80L ·
loop/README 100L · each rules card 50L · each wiring card 60L · DECISIONS ≤48 entries.

## Changing THIS governance (caps, fold rules, admission test) = CEO gate #8 —
`CEO-APPROVED:` commit token + manifest regen. One-time restructure precedent: e21d5ad +
the 2026-07-01 fold (see the DECISIONS header addendum).
