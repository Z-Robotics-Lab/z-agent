# DEBUG — compound fetch-place PLACE-leg walk-loop (R184, STATUS next #1)

## OBSERVE
- Symptom (R183 refuted row, `fetch-place.nl-compound` RAN 1/4, commit 61fde80):
  single utterance `把红色的罐子拿过来放到架子上` (fetch red can AND place on shelf) →
  GRASP leg CAUSED (`holding_object('red_can')`, eyes_combo.png), then the PLACE leg
  "degenerated to a walk-loop + navigate `at_position(10,5)` UNCAUSED → RAN 1/4".
- History: E7(R169) fixed "drops the trailing place clause"; E9/E10(R171/172) were
  harness ANSI-sync artifacts (fixed). R174 got 3/4, R183 got 1/4 → genuinely flaky.
- Code (bare-cli path = native_loop.py, planner-free tool-calling loop):
  - `_native_system_prompt` (native_loop.py:1030) assembles TWO guidance blocks for a
    manipulation world: `place_guidance` (1072-1084: grasp→`mobile_place`→verify
    `resting_on_receptacle`, "never finish after only the grasp") and
    `locomotion_guidance` (1091-1117): **"To REACH a place or coordinate (x, y), call
    navigate(x, y) ... RECOVER: if a verify returns FAIL, call navigate AGAIN and
    re-verify, repeating until at_position PASSES. NEVER call finish while FAIL."**
  - `_MAX_NATIVE_TURNS = 24` (native_loop.py:65) caps the loop → the run ends RAN, not
    a true infinite loop.
  - `mobile_place` (skills/mobile_place.py) is heavily honesty-gated; its verdict
    predicate is `resting_on_receptacle`, NOT `at_position`.

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|---|---|---|
| H1 | The place clause `放到架子上` is routed to `navigate`, not `mobile_place`, because `locomotion_guidance` invites "To REACH a **place** or coordinate (x,y), call navigate" and its unbounded RECOVER loop ("navigate AGAIN ... until at_position PASSES, NEVER finish while FAIL") traps the model on a self-invented `at_position(10,5)` until the 24-turn cap → RAN. `place_guidance` never forbids using navigate for a place. | prompt-conflict | the word "place" appears in BOTH guidance blocks with contradictory routing; R183 verdict was a `navigate`/`at_position(10,5)`, never `resting_on_receptacle` |
| H2 | Pure model nondeterminism / temperature. | model-variance | R174 3/4 vs R183 1/4 |
| H3 | `mobile_place` execution bug (walk-loop inside the place skill). | skill-exec | — |

## EXPERIMENT
- H3 falsify: the R183 recorded verdict predicate was `at_position(10,5)` (a navigate
  verify), NOT `resting_on_receptacle`; `mobile_place` was never invoked (its verdict
  would read `resting_on_receptacle`). → **H3 REJECTED.**
- H1 falsify: does any guidance forbid routing a place clause to navigate/walk?
  Read native_loop.py:1072-1117 — `place_guidance` says only "call mobile_place";
  `locomotion_guidance` actively frames navigate as the way to "REACH a place or
  coordinate (x,y)" and RECOVER-loops on at_position. The collision is in the code.
  → **H1 CONFIRMED** (root cause: guidance cross-talk on the word "place").
- H2: variance is real but the FAILURE MODE is fully explained by H1's collision;
  removing the collision should raise the success rate. Contributing factor, not the
  root cause; not separately actionable this round.

## CONCLUDE
- Root cause: `_native_system_prompt` (native_loop.py:1088-1117) teaches navigate as
  the route to "REACH a **place** or coordinate", colliding with the place clause; the
  model construes `放到架子上` as a nav destination, invents `at_position(10,5)`, and the
  unbounded navigate-RECOVER loop burns all 24 turns → RAN. `mobile_place` never runs.
- Fix (native_loop.py, NON-spine): (1) `place_guidance` gains an explicit prohibition —
  a "place on <receptacle>" clause is handled ENTIRELY by `mobile_place` (it walks
  there itself); do NOT use navigate/walk/at_position to "reach the shelf". (2)
  `locomotion_guidance` drops the word "place" so navigate is described only for an
  explicit coordinate / named location the USER gave — no cross-talk with place clauses.
- Regression test: `tests/unit/vcli/test_native_loop.py` — assert the manipulation-world
  prompt forbids navigate/walk for the place clause AND that locomotion guidance no
  longer offers navigate as the way to reach "a place".
- Verify command: `scripts/run-tests tests/unit/vcli/test_native_loop.py` (unit) +
  real-face `tools/acceptance/repl_accept.py MODE=combo` (bare vcli + NL, eyes on sim).
