# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-place-accept — PLACE RE-ACCEPTED on the bare REPL → the D163/D164 acceptance-gap saga is
CLOSED: BOTH fetch AND place now re-verified on the true face (bare vector-cli + NL, in-process, glfw fix in).
PLACE campaign (repl_accept.py MODE=place, place-only fresh sessions, 08:56-10:00): 6/6 verified=True (2/2 grounded)
across all 3 colours × 2, moat oracle resting_on_receptacle ✓ each (reads MuJoCo GT — actor cannot author),
launch_explore_seen=False + leak=none all 6 (in-process proof), eyes-confirmed (red_2/blue_2 frames: object resting
on receptacle, dog upright). FETCH re-accepted prior round: 6/6 True across 3 colours, eyes-confirmed, in-process.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D163/D164 acceptance gap CLOSED — fetch+place both re-accepted on the bare REPL. Frontier is next.
owns:    hardware/sim/go2_inprocess.py (single-source builder + reconcile_render_backend), hardware/sim/mujoco_go2.py
         (viewer guard), vcli/cli.py, vcli/tools/sim_tool.py, hardware/ros2/runtime.py, tests/**, scratchpad/**, docs/*.
         Spine vcli/cognitive/ FROZEN.
blocked: none. CEO gates queued below — do NOT cross.
next:
  1. [DONE] D163 C(b) single-source builder + runtime teardown fix (D166). Bare-REPL launch_explore EMPTY.
  2. [DONE] glfw fix (gui=True EGL/GLFW contention, adcd04b). FETCH RE-ACCEPTED 6/6 across 3 colours, eyes, in-process.
  3. [DONE] PLACE RE-ACCEPTED on bare REPL: 6/6 verified=True (2/2), 3 colours × 2, resting_on_receptacle GT oracle,
     launch_explore EMPTY + no leak, eyes-confirmed. Both floors now met on the true face (D167).
  4. [NOW — FRONTIER, probe done] Bar is met → RAISED it: harder-NL probe "把罐子放到架子上" (category-only, no colour,
     must disambiguate the unique 罐子 among 3 objects). HONEST result: disambiguation WORKS (resolved → pickable_can_red
     correctly); but verified=False (1/2) — resting_on_receptacle(can_red,'shelf')✓ passed while holding_object did NOT
     ground → the can rests on the shelf where it likely already sat, so the full pick+move did not ground (honest
     partial, not a fake). SEED next round: harden find-fetch-place so category-only refs get a full grounded pick+place
     — investigate (i) did the pick stage fail for the can, (ii) does "架子" resolve to the can's CURRENT surface making
     the place predicate trivially satisfied (receptacle-resolution gap). Then N≥5 3-colour category-only re-accept.
  5. [LATER FRONTIER] (b) VLN/SysNav multi-room; (c) 2nd embodiment g1 config-only registration (Invariant 3 test, S4
     gate); (d) BYO model/skill. Track B guardrails (G1..G5) still queued (G3↔C(b) VECTOR_NO_ROS2 reconcile noted).
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
