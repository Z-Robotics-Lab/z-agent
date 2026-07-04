# DEBUG — ord-posinv SCENE_SWAP regression (R299, STATUS next#1)

Bar: fetch.nl-ordinal-position-invariance (`把最左边的瓶子拿过来` under VECTOR_SCENE_SWAP).
R210 GROUNDED 2/2 (age73) → R284 REFUTED 0/2. Question: grasp-EXECUTION vs
target-SELECTION under swap.

## OBSERVE (from var/evidence/R284, cold — no interpretation)
SCENE_SWAP swaps ONLY the two bottles' (x,y): `_SCENE_SWAP_BODIES=(blue,green)`
(mujoco_go2.py:269). So post-swap leftmost bottle = BLUE (E43/E44). Yellow/red/purple
unmoved. Resolver = `_resolve_ordinal_via_catalog` (perception_grasp.py:291): projects the
GT catalog to image cx from the live camera pose, filters to BOTTLES, picks leftmost → returns
`(colour,label)` → drives the PROVEN colour-grasp path.

R284 run2 (persisted repl.raw.log) verdict summary:
```
▸ perception_grasp → verify holding_object('pickable_bottle_blue') · (actor=CAUSED)  [blue=False]
▸ (no action)      → verify holding_object('pickable_bottle_yellow') ✓ (UNCAUSED)    [yellow=True]
verdict RAN verified=False (0/3 grounded)
```
Brain narration: "The leftmost bottle has been grasped successfully! According to the
verification, it's the yellow bottle." → perception_grasp emitted its target as BLUE
(the CAUSED verify is auto-attributed to it) yet the gripper physically holds YELLOW.
run1 (R284 log 0/10): empty gripper UNCAUSED.

Raw facts: target the skill reported = blue (CAUSED). Object physically held = yellow.
So target-SELECTION named blue; grasp-EXECUTION closed on yellow.

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|---|---|---|
| H1 | Target-selection CORRECT (resolver→blue); grasp-EXECUTION grabs the wrong physical object (yellow) under swap; brain wander is downstream noise | grasp-exec | R284 CAUSED verify names blue; yellow physically held |
| H2 | Target-selection WRONG: under swap the catalog-projection resolver picks yellow/other, not blue (cx sign / FOV) | target-select | resolver reads live positions but cx projection could misorder |
| H3 | Resolver→blue, blue's swapped spot out of head-cam FOV → blue colour-mask empty → colour-grasp falls back to nearest visible blob = yellow (y=3.11, FOV-marginal, E45/E46) | perception/FOV | yellow held is the FOV-marginal object; blue moved to green's central spot |
| H4 | Pure brain artifact (deepseek-v4-flash post-grasp wander): skill-direct grasp holds blue cleanly, only the REPL brain broke it | brain | run-to-run flake, R272/R273 non-determinism class |

## EXPERIMENT (skill-direct, LLM bypassed — isolates mechanism from brain)
`scratchpad/ord_swap_probe.py` under VECTOR_SCENE_SWAP=1, query=最左边的瓶子:
A prints the swapped catalog (confirm blue↔green); B calls `_resolve_ordinal_via_catalog`
directly → resolved (colour,label) = target-SELECTION; C runs PerceptionGraspSkill.execute;
D reads holding_object for ALL 5 pickables = grasp-EXECUTION. Falsifies: H2 if B≠blue;
H1/H3 if B=blue but D holds yellow/nothing; H4 if D holds blue cleanly.

## CONCLUDE
(pending experiment)
