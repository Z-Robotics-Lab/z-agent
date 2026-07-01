# DEBUG.md — red-can fetch "0/3 grasp ceiling" (D172) — is it really grasp physics?

## OBSERVE
- D172 concluded: on the bare REPL via DeepSeek, RED "把红色的瓶子拿过来" -> verified=False (0/3);
  green/blue grasp, red doesn't -> "GRASP ROBUSTNESS is the frontier / red-can pose/IK reach ceiling".
- Scene geometry (mjcf/go2/scene_room.xml): red is a CAN (pickable_can_red, radius 0.033, pos 10.9,3.22,0.32);
  green/blue are BOTTLES (radius 0.028, pos 10.88,3.0 and 10.9,2.78). There is NO red BOTTLE -- D172's utterance
  "红色的瓶子" (red BOTTLE) names a non-existent object; the red object is 罐子 (a can).
- Grasp mechanism (mujoco_gripper.py): weld fires within _GRASP_RADIUS=0.05m of the object CENTER -- width/radius
  is irrelevant to the weld; only EE-reaches-center matters. So "wider can -> can't grip" is not a mechanism.

## HYPOTHESIZE
| # | Hypothesis | Category | Evidence |
|---|-----------|----------|----------|
| H1 | Red-can grasp physics/IK genuinely fails (D172's claim) | Physics | D172 REPL 0/3 |
| H2 | REPL used the WRONG NL term "红色的瓶子" (red bottle, no such object); a higher layer fails, not physics | Model/NL | red obj is a can |
| H3 | REPL gui=True sim GL-contention (D164) degrades red perception only | Sim/env | probe is gui=False |

## EXPERIMENT (skill-direct probe = REAL mechanism, bypasses LLM/harness; scratchpad/grasp_probe.py, gui=False)
### H1: red-can grasp physics fails
- red-can correct term "红色的罐子" x3: skill_success=true, weld_formed=true, held=true (moat holding_object),
  grasp_world~(10.87,3.21,0.32) on the can, can LIFTED z 0.32->0.51..0.57, dog aligned to y~3.2-3.46. 3/3.
- plus the initial run = 4/4 grounded.
=> red-can grasp physics is ROBUST (4/4). **H1 REJECTED.** D172's "grasp ceiling" is wrong at the skill level.

### H2: wrong term / higher-layer, not physics
- red WITH the D172 wrong term "红色的瓶子" (red bottle), target pickable_can_red: perception STILL resolves
  detection_label=pickable_can_red, weld_formed=true, held=true, can lifted. Perception robust to the wrong term.
=> Neither term nor physics fails at the SKILL level. The 0/3 must be in the REPL model/routing/harness path
  (native-loop plan, model-authored verify target, or gui sim). **H2 partially confirmed (failure is above the skill).**

## CONCLUDE (interim -- pending bare-REPL REAL-VERIFY)
- Root cause is NOT grasp physics. Red-can grasp grounds 4/4 skill-direct. D172 mislabeled a REPL-path failure
  as a "grasp-robustness ceiling". Next: REAL-VERIFY red-can fetch on the BARE REPL by the CORRECT NL term
  "红色的罐子" via DeepSeek, N>=3, in-process (launch_explore EMPTY), eyes on the render. If it grounds -> all 3
  colours accepted on the true face and the "grasp ceiling" is disproven on the acceptance face.
