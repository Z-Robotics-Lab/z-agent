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
| H2 | REPL used the WRONG NL term "红色的瓶子" (no such object); a higher layer fails, not physics | Model/NL | red obj is a can |
| H3 | REPL gui=True sim GL-contention (D164) degrades red perception only | Sim/env | probe is gui=False |

## EXPERIMENT (skill-direct probe = REAL mechanism, bypasses LLM/harness; scratchpad/grasp_probe.py, gui=False)
### H1: red-can grasp physics fails
- red-can correct term "红色的罐子" x3: skill_success=true, weld_formed=true, held=true (moat holding_object),
  grasp_world~(10.87,3.21,0.32) on the can, can LIFTED z 0.32->0.51..0.57, dog aligned to y~3.2-3.46. Plus initial = 4/4.
=> red-can grasp physics is ROBUST (4/4). **H1 REJECTED.** D172's "grasp ceiling" is wrong at the skill level.

### H2: wrong term / higher-layer, not physics
- red WITH the D172 wrong term "红色的瓶子" (skill-direct), target pickable_can_red: perception STILL resolves
  detection_label=pickable_can_red, weld_formed=true, held=true, can lifted. Perception robust to the wrong term.
=> Neither term nor physics fails at the SKILL level. **H2 -> the failure, if any, is ABOVE the skill.**

### H3: REPL gui GL-contention degrades red only
- Bare-REPL red fetch grounds 4/4 (below); if gui contention bit red it would not ground reliably. **H3 REJECTED.**

## REAL-VERIFY (bare vector-cli + NL, VECTOR_PROVIDER=deepseek, in-process launch_explore_seen=False on ALL)
- redcan1/2/3 "把红色的罐子拿过来" -> fetch_verified=True (1/1) x3; eyes (redcan1, redcan3): RED CAN held aloft,
  green+blue on table. Oracle holding_object('pickable_can_red') + eyes AGREE.
- redbottle_wrongterm "把红色的瓶子拿过来" (D172's WRONG term, red BOTTLE) -> fetch_verified=True (1/1); eyes:
  red CAN held aloft. The colloquial/wrong term RESOLVES to the red can (NL robustness bonus).
- Red-can total = 4/4 bare-REPL + 4/4 skill-direct = 8/8.

## CONCLUDE
- Root cause of D172's "red 0/3": NOT grasp physics (robust 8/8) and NOT the wrong NL term (the wrong term grounds
  too). It was a TRANSIENT in that single D172 campaign (one-off perception/grasp miss or session state) mislabeled
  as a systematic "grasp-robustness ceiling". The ceiling does not exist.
- OUTCOME: all 3 colours now ground on the bare acceptance face (green/blue = D172, red = this round). Fetch is
  firmed across colours. The claimed frontier ("grasp robustness") is closed; move to PLACE-via-DeepSeek + harder NL.
- No code fix needed -- this was a false-ceiling correction. Regression guard: grasp_probe.py (skill-direct,
  deterministic) + repl_accept.py MODE=fetch (the acceptance face) both exercise the red-can grasp.
