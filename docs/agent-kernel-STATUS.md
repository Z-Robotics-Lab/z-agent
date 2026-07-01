# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-glfw — root cause of the bare-REPL grounding gap FOUND + FIXED + FETCH RE-ACCEPTED.
Gap was NOT the native-producer plan (STATUS H1 refuted: bottle 0.88m ahead, lone grasp is correct) — it was a
GL-backend contention: sim-launch defaults gui=True while offscreen render is EGL; EGL+GLFW viewer can't coexist →
perception renderer fails → detect no_detections → grasp RANs uncaused → verified=False. FIX: reconcile_render_backend
(go2_inprocess.py) binds glfw when a viewer+display are wanted, else keeps egl headless — set BEFORE mujoco import.
FETCH re-accepted on the BARE REPL (in-process, launch_explore EMPTY, post-fix 08:26-09:09): 6/6 True 1/1 across
all 3 colours (green/blue/red × 2 campaigns); 2 eyes-confirmed (green→green, blue→blue in gripper, others untouched).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D163 gate CLOSED. glfw fix in. FETCH re-accepted on bare REPL. PLACE re-acceptance IN PROGRESS this round.
owns:    hardware/sim/go2_inprocess.py (single-source builder + reconcile_render_backend), hardware/sim/mujoco_go2.py
         (viewer guard), vcli/cli.py, vcli/tools/sim_tool.py, hardware/ros2/runtime.py, tests/**, scratchpad/**, docs/*.
         Spine vcli/cognitive/ FROZEN.
blocked: none. CEO gates queued below — do NOT cross.
next:
  1. [DONE] D163 C(b) single-source builder + runtime teardown fix (D166). Bare-REPL launch_explore EMPTY.
  2. [DONE] Root-cause + fix the bare-REPL grounding gap = gui=True EGL/GLFW contention (DEBUG.md, commit adcd04b).
     FETCH RE-ACCEPTED: 6/6 True across 3 colours, eyes-confirmed, in-process. Skill 5/5 (gui=F), glfw fix 2/2 coexist.
  3. [IN PROGRESS] PLACE re-acceptance on bare REPL (place-only fresh sessions, 3 colours, resting_on_receptacle oracle +
     Qwen3-VL eyes, launch_explore EMPTY). /tmp/place_campaign2.sh driving repl_accept.py MODE=place.
  4. [THEN] Track B guardrails (G1..G5); frontier (robust find-fetch-place → VLN/SysNav → 2nd embodiment g1 → BYO model/skill).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true acceptance face, no -p/flag),
  measure_qwen.py (-p probe, NOT the face), place_probe.py. GOTCHAS: `pgrep -f launch_explore` matches the loop's own
  claude -p argv (goal text) — match `launch_explore\.sh` + exclude claude; pexpect needs codec_errors='replace';
  REPL verdict renders `verified=True/False (n/m grounded)` with ANSI splitting `=`; `rosm nuke` between sims.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **D106** receptacle place oracle: spine piece APPROVED+BUILT+moat-proven (D116); non-gated plumbing REMAINS (verify
  namespace · height receptacle · arm↔table descent · bare-cli pick-AND-place). Else place = grasp→release.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed +
  `config/worlds/<world>.yaml` + unify SceneGraph store (retire WorldModel/SysNav). Keys → core/scene_graph.py, perception/object_localizer.py.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
