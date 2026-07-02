# Red-team — refutation-first check on every headline claim (pull BEFORE recording one)

A "headline claim" = any metric, benchmark, N/M rate, "it works", "accepted", "closed", or a
refutation of a prior entry. The claim's author is the worst person to confirm it — so attack it.
Harnesses with a native red-team skill MAY use it in addition; this card is the contract.

## The checklist (run each attack; a claim records only what survives)
1. **Falsify, don't confirm.** Design each check to DISPROVE the claim. Never "run it again and
   see if it still passes" — pick the input/condition most likely to break it.
2. **Check the harness before the physics.** When a result surprises, suspect the measuring
   instrument first (D171/D172→D174: a "model-sensitivity ceiling" was a harness artifact;
   the wrong-NL-term "grasp ceiling" was a transient mislabeled as systematic).
3. **Check who authored the verify target.** If the actor chose the object AND wrote the
   predicate call, the oracle certifies self-consistency, not intent (D69 fakeable-grasp,
   D182 actor-authored-target gap). Ask: could a wrong actor pass this gate self-consistently?
4. **Check verdict provenance.** Which command, which env, which face? A flag/-p/script number
   is NOT a bare-REPL number (the D163/D164 downgrade: all prior rates were flag-path). Record
   face + provider + env with the number, or the number is unanchored.
5. **Run a discriminating control.** One positive control (the mechanism CAN fire) and one
   negative/confound control (the effect vanishes when its cause is removed — D182 neg_green
   refuted the can-bias confound). A claim without a control is an anecdote.
6. **Report pass@N with N, verbatim.** 2/2 is not "100%"; 0/3-then-8/8 is a transient, not a
   ceiling. Never round up, never drop the denominator.
7. **Eyes on the evidence.** For any physical claim, look at the frames/data, and record the
   eyes mode honestly: vlm-judge | self-read | human. Self-read is witness-grade, not
   oracle-grade — say so in the row.
8. **A refutation is itself a headline claim.** Red-team it the same way before un-banking a
   prior entry (D180's billing mis-correction needed its own correction).

## What survives → how to record
- Bank the result as a `provisional` ledger row (loop/ledger/) in the SAME round, with the
  `redteam:` field describing the attack that failed to kill it.
- Promotion to `confirmed` / DECISIONS [RULING] happens NEXT round (loop/ROUND.md §1) — never
  in the round that formed the conclusion.
- A claim that DIES under red-team is a finding, not a failure: record the refuted row with
  `do_not_retry_unless` filled. Refuted rows are the memory that prevents re-exploration.
