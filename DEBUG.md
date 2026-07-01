# DEBUG.md — category-only fetch/place does not ground (罐子 grasps the wrong object)

## OBSERVE
- Repro (bare REPL, in-process, scratchpad/repl_accept.py MODE=fetch): "把罐子拿过来"
  → verified=False (0/3). launch_explore EMPTY (in-process took). Model authored the
  CORRECT verify label holding_object('pickable_can_red') (82× in trace) → disambiguation
  at the verify level WORKS.
- Eyes (verdict_*.png): the gripper holds the BLUE bottle; the red can is knocked to the
  floor at far right. So the grasp secured the WRONG object → holding_object('pickable_can_red')
  is honestly False. The gap is ACTOR-side object selection, not the verify.
- Perception probe (scratchpad/dino_probe.py, real Go2GraspPerception frame):
  objects blue y=2.78 (cx264), green y=3.0 (cx160), red_can y=3.22 (cx57).
  grounding-dino for prompt "a can." (= query_to_prompt("罐子")):
    red_can cx57 conf=0.537 · blue cx264 conf=0.522 · green cx160 conf=0.513.
  The real can ranks first but by a NOISE-THIN 0.02 margin — all 3 pickables are near-identical
  cylinders, so "a can." cannot reliably single out the can. Raw "罐子" → [] (dino is English).
- Contrast: the colour path grounds 6/6 (D167) because HSV colour is a STRONG discriminator.

## HYPOTHESIZE
| # | Hypothesis | Evidence |
|---|-----------|----------|
| H1 | verify label wrong (holding_object('罐子')) | REJECTED — model authored 'pickable_can_red' |
| H2 | colourless perception picks wrong cylinder (max-conf among ~equal "can" boxes) | CONFIRMED — probe 0.537/0.522/0.513, eyes show blue grabbed |
| H3 | grounding-dino can't handle Chinese | partial — raw 罐子→[]; but query_to_prompt maps 罐子→"a can." so the real path is English (not the cause) |

## EXPERIMENT
- H2 check: dino_probe.py printed per-prompt boxes. "a can." gives all 3 cylinders ~0.51-0.54
  (margin 0.02 = noise). _select_detection(color=None) = plain max-conf → effectively random
  among the 3. → H2 CONFIRMED. Shape alone does not disambiguate identical cylinders.

## CONCLUDE
- Root cause: a colourless category reference ("罐子"=can) routes to grounding-dino "a can.",
  which scores all 3 near-identical cylinders equally; max-confidence selection then grabs a
  random one (blue observed). Colour is the reliable discriminator; category alone is not.
- Fix (actor-side, non-gated, moat-safe): resolve a UNIQUE-category reference against the scene's
  object catalog (the arm's GT object-name set — config the actor cannot author) to its single
  matching object AND its colour attribute, then drive the PROVEN colour-selection path (HSV +
  _COLOR_TO_SCENE). "罐子" → unique can = pickable_can_red (red) → colour path → reliable grasp.
  Ambiguous categories ("瓶子" = 2 bottles) resolve to None → unchanged (honestly can't pick one).
  The verify oracle holding_object(...) is BYTE-UNCHANGED and independently grades the GT weld —
  the resolver can only change WHICH object is grasped, never fake a verdict (moat holds).
- File:line: vector_os_nano/skills/perception_grasp.py (execute: colour resolution) +
  grounding_dino._ZH_NOUN_EN (noun map, reused).
- Regression test: unit test the category→(colour,name) resolver; then bare-REPL re-accept
  category-only fetch "把罐子拿过来" grounds holding_object('pickable_can_red'), eyes-confirm,
  launch_explore EMPTY; re-check colour cases un-regressed (resolver only fires when color is None).
