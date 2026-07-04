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

## EXPERIMENT RESULTS (skill-direct, VECTOR_SCENE_SWAP=1 then control no-swap)
SWAP (var/evidence/R299/ord_swap_probe.log):
- catalog: blue[10.88,3.0] green[10.9,2.78] yellow[10.9,3.11] (swap moved blue↔green only)
- resolved (step B) = `(None, pickable_bottle_yellow)` — resolver picks YELLOW, not blue
- held (step D) = yellow:True, all others False; skill_success=True, weld_formed=True,
  grasp_world=[10.877,3.108,0.322]≈yellow. GRASP CLEAN.
NO-SWAP control (ord_noswap_probe.log): resolved = YELLOW, held yellow:True, weld_formed. SAME.

## CONCLUDE
ROOT CAUSE: NOT grasp-execution and NOT a resolver bug — a SCENE-EVOLUTION STALE EXPECTATION.
The resolver is CORRECT: among the 3 bottles {green, blue, yellow}, image-cx DECREASES as
world-y INCREASES (E31/E33 baseline leftmost=green@y3.0 over blue@y2.78), so leftmost bottle =
highest-y = YELLOW (y=3.11) in BOTH baseline and swap. Grasp-execution is CORRECT: it holds the
resolved target (yellow) cleanly, weld formed, in both runs.
The regression is an artifact of the BAR, not the code: the yellow bottle was ADDED at R211
(y=3.11) — AFTER the ord-posinv bar was fixed at R209/R210 with only green+blue (then leftmost
under swap = blue@y3.0). Yellow at 3.11 is more-left than blue at 3.0, so it silently became the
true leftmost bottle. Worse, yellow is UNMOVED by the swap, so the swap no longer probes
position-invariance at all (answer = yellow regardless). R284 "held wrong YELLOW" = the resolver
correctly grasping the real leftmost; R284's blue verify was the BRAIN's guess, not the skill's
resolution (my OBSERVE misread the CAUSED verify). R284 run1's empty gripper = a separate brain
thrash (never completed a grasp), not a mechanism fault.
Hypotheses: H1 REJECTED (grasp-exec correct). H3 REJECTED (blue central/imageable; yellow won on
genuine cx, no fallback). H4 PARTIAL (run1 empty = brain; run2 yellow = correct resolver, not
brain). H2 mechanism-CONFIRMED but REFRAMED: resolver picks yellow, and that is CORRECT for the
current scene — the stale artifact is the bar's expected-blue.

FIX/RESOLUTION (no code change to the spine): the bar `fetch.nl-ordinal-position-invariance` is
OBSOLETE as written (already `superseded` on BOARD). Two honest options for a future ord-posinv
probe: (a) EXCLUDE the unmoved yellow (query `最左边的瓶子` among only the swapped pair, or make
the swap include yellow) so the swap actually flips the answer; (b) update the expected target to
the true live leftmost (yellow) — but then it stops testing invariance. No grasp/perception fix
is warranted; the mechanism grounds skill-direct 1/1 (+control 1/1).
Regression guard: a unit test asserting `_resolve_ordinal_target` picks the highest-world-y bottle
given the current 3-bottle catalog would have flagged the expected-blue as stale when yellow landed.
