# CEO gates — what stops the loop, how to queue it, who decides (pull when you hit one)

A gate = a decision class the round agent NEVER crosses autonomously. Hitting one is normal:
queue it, pivot to non-gated work, keep progressing. Stopping to ask "continue?" is a defect;
stopping at a gate is the design.

## The gate list (never narrower than this)
1. New/changed public interface (msg/srv/action, CLI contract, MCP tool schema, World protocol).
2. Cross-package data-flow change.
3. New external dependency.
4. Hardware interface change.
5. Security policy change (permissions layers, secrets handling, network surfaces).
6. Honest-verify-spine semantics — ANY diff to the spine paths enumerated in loop/check.sh,
   any predicate/oracle semantics change, anything that could make verify LOOSER. Additions
   must be stricter-only, and still gate.
7. Release to main / push to a shared remote.
8. Rewriting an accepted DECISIONS ruling or changing doc-governance semantics (fold rules,
   caps, admission test).

## How to queue (the executive summary — ≤10 lines, into STATUS.md `gates:`)
```
GATE <short-name> (<gate class>) — queued R<n>
What: one line. Why now: one line.
Options: A (recommended, because …) vs B.
Impact: files/interfaces touched. Risk: one line.
Evidence: ledger row / commit / DEBUG.md pointer.
```
Batch queued gates; the owner adjudicates asynchronously. A gate answer is recorded as a
DECISIONS [RULING] entry (the owner's call, the round writes it down verbatim).

## Who decides
- The repo owner (CEO/CTO). A solo cloner is their own CEO: the gate still means STOP,
  decide deliberately OUT of the loop (not mid-round momentum), record a [RULING], only
  then proceed. The value is the pause + the written ruling, not the org chart.

## Gate tokens are tamper-EVIDENT, not tamper-proof (honesty note)
`GATE-APPROVED:` / `CEO-APPROVED:` in a commit body unlock loop/check.sh for gated surfaces.
They are audit trails, not physical locks — a misaligned agent could write the string. The
compensating controls: the supervisor's post-round check runs unconditionally; every review
round audits `git log --grep='GATE-APPROVED\|CEO-APPROVED'` since the last review and lists
any self-approval in STATUS `gates:` for the owner. Do not mistake the token for a guarantee;
do not remove the audit.
