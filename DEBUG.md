# DEBUG — R196: isolate the ordinal→colour grasp-EXECUTION miss (green knocked to floor)

## OBSERVE
- STATUS next#1: R194+R195 both knocked the ordinal target to the FLOOR (verified=False)
  though SELECTION was correct (R195b targeted green). Frontier: "why green misses on the
  ordinal→colour path despite R190 grasp-reliable".
- R192 green ordinal GROUNDED 1/1 (single sample). R194 REFUTED robustness. R195 SELECTION
  fixed (passthrough+resolver) but grasp missed 1/2.
- Scene geometry (go2_room.xml:636-651): green bottle r=0.028, blue bottle r=0.028,
  red can r=0.033 (5 mm wider radius). Comment: thin bottles (<2.5 cm) can't be held by the
  35 mm Piper jaws under position control; the weld (radius 60 mm) is the hold.
- R190/R191 "grasp-reliable" target = the RED CAN. Green BOTTLE grasp was NEVER established at
  N>=2 — the only green-bottle success is R192's lone 1/1.

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|---|---|---|
| H1 | The ordinal->colour path executes a DIFFERENT grasp than plain-colour (query leaks into grasp-point selection) | code-path | STATUS frames it as "ordinal->colour path misses" |
| H2 | The miss is green-BOTTLE grasp reliability (marginal weld / lateral knock), independent of ordinal; R192 1/1 was a lucky sample | grasp-geometry | red can r=0.033 reliable vs green bottle r=0.028; N=1 never establishes reliability |
| H3 | The ordinal resolver picks a non-green so the "miss" is a mis-selection | selection | STATUS says selection was correct in R195b |

## EXPERIMENT
### H1 — code read (is `query` inert once `color` is resolved?)
perception_grasp.py: `_resolve_ordinal_via_catalog` -> `(color,label)`; caller sets
`color=ordinal_hit[0]` (L1059) then drives the SAME `_perceive_with_scan(...,color=color)`.
In `_perceive_grasp_point` (L1620): `use_front_resolver = have_front and (deictic or color is
not None)` -> with color set, the HSV `front_object_mask(rgb,depth,color=color)` computes the
mask/point; `query` is used ONLY for the verify LABEL fallback + logging, NOT the mask/3D point.
-> H1 REJECTED: once color=green is resolved, the ordinal path and the plain-colour path execute
a byte-identical grasp. "ordinal->colour path misses" is a MISATTRIBUTION.

### H2 — probe plain-colour green N times (scratchpad/grasp_probe.py, default 绿色的瓶子 /
pickable_bottle_green; VLM stubbed -> isolates GRASP from NL routing; reads holding_object).
Prediction if H2 true: plain-colour green also misses a meaningful fraction. -> result pending.

### H3 — grasp_probe reads holding_object on the NAMED target; a mis-selection shows as a
wrong-object hold, not a floor knock. R195b already re-confirmed green targeted. -> deprioritized.

## CONCLUDE (H1+H2+H3 all REJECTED — the premise was wrong)
- H1 REJECTED (code): once color=green resolves, ordinal path == plain-colour path.
- H2 REJECTED (probe): plain-colour green grasp 4/4 held; green geometry is NOT unreliable.
- H3 REJECTED (probe): '最左边的瓶子' skill-direct -> detection_label=pickable_bottle_green,
  held=True, weld=True, lifted 0.32->0.56, grasp_world=[10.857,3.001,0.322] dead-on. 5/5 total.

ROOT CAUSE (one sentence): perception_grasp GROUNDS the green ordinal reliably; the R194/R195
verified=False is the BRAIN routing a `handover` AFTER a successful grasp (reading '拿过来' as
bring-to-user), and handover RELEASES the weld, so the terminal holding_object verdict reads
False — the "grasp missed / knocked to floor" symptom pointed AWAY from the real cause.
- Evidence: R195b REPL log — "The grasp succeeded" -> home -> verify holding_object (passed)
  -> "拿过来 means bring it here ... Let me hand it over" -> handover(direction=right) ->
  "The handover released the bottle" -> final holding_object -> verified=False.
- Model-strategy variance (E9/E10/E21 trap): R192 deepseek-CHAT grasped the IDENTICAL utterance
  '把最左边的瓶子拿过来' and STOPPED at the hold -> GROUNDED; R194/R195 deepseek-v4-FLASH added a
  handover. So E30 "robustness REFUTED" was a MODEL change (chat->v4-flash), not grasp flakiness.

FIX (file): vector_os_nano/vcli/native_loop.py grasp guidance — "BRING / FETCH IS COMPLETE
AT THE HOLD" clause: a bare 拿/拿来/拿过来 (no place clause, no explicit hand-over) is satisfied
when holding_object PASSES; do NOT call handover (it releases the weld); handover ONLY on an
explicit 递给我/给我/hand-it-to-me. Non-spine, verify oracle byte-unchanged.

REGRESSION TEST: tests/unit/vcli/test_native_loop.py::test_bring_is_complete_at_the_hold_no_auto_handover — the manipulation-world grasp
prompt teaches "do NOT call handover" for a bare fetch and reserves handover for 递给我/给我.

VERIFY: bare-REPL '把最左边的瓶子拿过来' (deepseek-v4-flash) -> grasp, NO handover, verified=True.
