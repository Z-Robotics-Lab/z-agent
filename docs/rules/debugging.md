# Debugging — the Hypothesis Loop (pull on any non-obvious bug; not for typos/build errors)

Trigger: a test failure that isn't an obvious typo, "it doesn't work" with unclear cause, any
symptom that survived one honest fix attempt. The #1 failure this prevents: bulldozing through
a wrong theory. Record the whole loop in DEBUG.md (repo root, overwritten per debug session).

## OBSERVE — collect, don't interpret
- Reproduce first. Record the EXACT error text (never paraphrased), minimal repro steps,
  `git log --oneline -10` + `git diff` (what changed recently), and the domain snapshot
  (sim: pgrep/free -g/frame; perception: mask px + depth at the projected pixel; model:
  provider + raw response).

## HYPOTHESIZE — 3-5 causes, each WITH evidence from OBSERVE
- No hypothesis without a supporting observation. Rank by evidence strength, then by ease of
  falsification. Check docs/tricky-bugs.md — the symptom may be a documented signature
  (e.g. "detected far, lost near" = FOV geometry, not the detector).

## EXPERIMENT — one falsifying check per hypothesis, one at a time
- Design each check to DISPROVE the hypothesis; never bundle two; never "apply a fix to see
  if it helps" (that's confirming, not falsifying).
- One command or minimal probe per check. Record the result immediately:
  `→ [result]. H<N> CONFIRMED / REJECTED.` All rejected → back to OBSERVE with new data.

## CONCLUDE
- Root cause in one sentence + exact file:line. Minimal fix. A regression test that would
  have caught it. Verify: suite green + the original repro now passes.
- Symptom pointed AWAY from the cause / survived a green suite? → add a docs/tricky-bugs.md
  case (3-6 lines: symptom → why hidden → root → fix → lesson).
- Same failure twice → STOP retrying variants; write the DEBUG.md, then escalate (or in a
  loop round: bank an experiments row with status:inconclusive + what was ruled out).

## DEBUG.md skeleton (overwrite per session)
```markdown
# DEBUG.md — <short description>
## OBSERVE
- Repro: · Error: · Snapshot: · Recent changes:
## HYPOTHESIZE
| # | Hypothesis | Category | Evidence |
## EXPERIMENT
### H1: <name>  → result. **H1 REJECTED/CONFIRMED.**
## CONCLUDE
- Root cause: · File:line: · Fix: · Regression test: · Verify command:
```
