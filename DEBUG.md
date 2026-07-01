# DEBUG.md — bare-REPL fetch/place grade verified=False (perception_grasp ran_no_weld)

## OBSERVE
- Repro (bare REPL, in-process, no -p/flag): `启动带手臂的 go2 仿真` → `把绿色的瓶子拿过来`.
- Verdict (dbg1, raw log): `perception_grasp → verify holding_object('pickable_bottle_green') · (actor=UNCAUSED)`
  → `RAN verified=False (0/1 grounded)`. Place likewise: grasp UNCAUSED → mobile_place NOT_GRADED → 0/2.
- Producer trace: model called `perception_grasp (query=绿色的瓶子)` as the SOLE action then finish — EXACTLY
  as native_loop.py:1090-1105 instructs (grasp-first, do NOT navigate; perception_grasp self-approaches).
- Geometry (go2_room.xml + mujoco_go2.py:374): spawn (10.0,3.0); green bottle (10.88,3.00,0.320) →
  planar dist ~0.88 m, WELL inside perception_grasp's ~1.6 m self-approach reach. Object IS in reach.
  → REFUTES STATUS H1 ("bottle across the room, needs navigate"): default scene is near, lone grasp is correct.
- Root symptom: perception_grasp RUNS to completion but forms no gripper weld → holding_object stays False
  (result_data diagnosis 'ran_no_weld', perception_grasp.py:1052). D156 measured this exact near geometry at 0.93;
  D166's bare-REPL 0/1 was N=1.

## HYPOTHESIZE
| # | Hypothesis | Category | Evidence |
|---|-----------|----------|----------|
| H1 | Missing navigate before grasp (far object) | plan | REFUTED a priori: bottle 0.88 m ahead, in reach; lone grasp is by-design for near |
| H2 | perception (Moondream detect) misses green bottle some runs → no_detections | perception | grasp is perception-driven; stochastic VLM |
| H3 | perceived+approached but weld misses by a few mm (ik/grasp-radius residual) → ran_no_weld | grasp reliability | diagnosis 'ran_no_weld'; skill has retry/nudge for exactly this |
| H4 | True rate ~0.9 (D156) and bare-REPL 0/1 was N=1 noise | measurement | D156 0.93 on same geometry; single sample |

## EXPERIMENT
- E1: skill-direct grasp_probe (gui=FALSE, no LLM) x5 on the exact acceptance geometry+query.
  → RESULT: **5/5 GROUNDED** (weld_formed+held all true, bottle lifted 0.32→0.56, ~30-35s, diagnosis=ok).
  So the GRASP SKILL is rock-solid on this geometry. H2/H3 REJECTED as the dominant cause; H4 (skill fine) supported.
  ⇒ The bare-REPL 0/1 is NOT a skill defect. The failure is in the bare-REPL PATH, not the skill.
- E2: what differs in the bare-REPL path? Found: SimStartTool._start_go2 + build_inprocess_go2_agent DEFAULT
  **gui=True** (sim_tool.py:166, go2_inprocess.py:37) → a GLFW viewer window whose GL context can starve the
  perception renderer's EGL context (D164: "Failed to make the EGL context current"). My probe used gui=False.
  New H5: gui=True degrades perception → grasp point off / mask degraded → grasp RANs (actor=UNCAUSED with a
  grasp_world, consistent with the bare-REPL trace: it perceived+approached but no weld).
- E3: grasp_probe with PROBE_GUI=1 (gui=True, matching the bare-REPL) x3 — does it reproduce the failure? [RUNNING]

## CONCLUDE
- (pending E3) — leading root cause H5: bare-REPL sim-launch gui=True starves perception EGL context.
