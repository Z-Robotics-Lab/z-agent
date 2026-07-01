# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D166 — D163 sim-launch split-brain CLOSED (C(b) done): the bare `vector-cli` REPL + NL now
builds the PROVEN in-process MuJoCoGo2 via ONE shared helper (Rule 3/11); `launch_explore` EMPTY confirmed live.
BUT re-acceptance surfaced a DEEPER gap: bare-REPL fetch/place EXECUTE in-process yet grade verified=False
(fetch 0/1, place 0/2) — the native producer routes fetch to a lone perception_grasp with NO navigate/approach,
so holding_object never trues. fetch/place are NOT re-accepted. Extraction proven faithful (deterministic build).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D163 gate CLOSED. Acceptance-face fetch/place grounding gap OPEN (native-producer plan, not sim-launch).
owns:    hardware/sim/go2_inprocess.py (NEW, single-source builder), vcli/cli.py, vcli/tools/sim_tool.py,
         hardware/ros2/runtime.py, tests/vcli/tools/**, scratchpad/**, docs/*. Spine vcli/cognitive/ FROZEN.
blocked: none (next chunk is non-gated debugging). CEO gates queued below — do NOT cross.
next:
  1. [DONE] D163 C(b): single-source build_inprocess_go2_agent; sim_tool._start_go2 routes to it on VECTOR_NO_ROS2=1;
     cli._init_agent uses it + keeps ROS2 tail; runtime.py teardown fix. Unit green; bare-REPL launch_explore EMPTY.
  2. [NEXT] DEBUG the acceptance-face grounding gap (Hypothesis Loop). H1: native producer omits navigate_to_object
     before perception_grasp (fetch was 1 step) — bottle across room, grasp misses. H2: perception_grasp gets no 3D
     localize (look not run) → names-only, grasp to nowhere. H3: -p vgg path also 0/1 (1 slow sample, inconclusive).
     Isolate: run navigate_to_object→perception_grasp directly (skill/-p), watch holding_object; then fix the native
     plan so fetch = look→navigate→grasp. RE-ACCEPT on bare REPL: 3 colours N>=5, Qwen3-VL eyes, launch_explore EMPTY.
  3. [THEN] Track B guardrails (G1..G5); frontier (robust find-fetch-place → place → VLN/SysNav → g1 → BYO model/skill).
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
