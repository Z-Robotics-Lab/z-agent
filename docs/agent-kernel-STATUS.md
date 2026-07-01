# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D164 — #1 OPEN ITEM = the ACCEPTANCE-FACE GAP. Prior FETCH (0.93/0.87) + PLACE (8/8) were on the
FLAG-GATED `--sim-go2` in-process sim, NOT the bare `vector-cli` REPL + NL → DOWNGRADED to "not yet re-accepted".
Pipeline: routing=Qwen(qwen-max) + eyes=Qwen3-VL-plus via DashScope (QWEN_API_KEY + VECTOR_PROVIDER=qwen; DeepSeek-
direct + OpenRouter dead). Self-dev loop-driver = maintainer's PRIVATE harness OUTSIDE this repo (a clone neither has
nor needs it); loops STOPPED until C(b) re-acceptance lands.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   Post-fetch-place. Skills work in-process (perception_grasp+R11 retry; mobile_place+R14/R15; moat
         resting_on_receptacle D106/D116). The gap is the acceptance FACE (D163 Rule-3/11 split-brain).
owns:    skills/{perception_grasp,navigate_to_object,mobile_*}.py, vcli/tools/sim_tool.py, tools/acceptance/**,
         acceptance/**, docs/*. Spine vcli/cognitive/ FROZEN.
blocked: bare-cli fetch/place — awaiting Track C(b) (D164). CEO gates queued below — do NOT cross.
next (D164, approved A->C->B; A DONE):
  1. [DONE] Self-dev loop-driver hardened (private, outside-repo; systemd Restart=always + per-dir lock + never-kill;
     verified). No loop RUNNING until step 2 lands.
  2. [NEXT] CLOSE D163: SINGLE-SOURCE extract cli.py's in-process go2+arm build (cli.py:747-888) into ONE helper;
     make sim_tool._start_go2 (sim_tool.py:476-654) call it on VECTOR_NO_ROS2=1 (NOT a copy). Keep ROS2 path + parity
     e2e; fix runtime.py:132/139 teardown. RE-ACCEPT fetch+place on the BARE REPL (`pgrep -f launch_explore` EMPTY),
     3 colours, N>=5, Qwen3-VL eyes, red-team. Non-gated; this IS the gate.
  3. [THEN] Track B guardrails (G1..G5) make bare-cli+NL un-bypassable; then the #3 frontier.
tooling (scratchpad/, git-tracked): place_probe.py, measure_qwen.py (+ run_*.sh). GOTCHAS: don't pre-`pkill vcli.cli`
  inline; `rosm nuke` between sims, NEVER pkill mujoco; serialize sims; commit every change. Contracts/G1/facts → ARCH.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **D106** receptacle place oracle: spine piece APPROVED+BUILT+moat-proven (D116); non-gated plumbing REMAINS (verify
  namespace · height receptacle · arm↔table descent · bare-cli pick-AND-place). Else place = grasp→release.
- **find-and-grasp #4/#5 (OPEN, CEO-gated — from plan-find-grasp, NOT done):** #4 external-explore integ + persist +
  `/rebuild`; #5 startup room-seed + `config/worlds/<world>.yaml` + unify SceneGraph store (retire WorldModel/SysNav).
  Reuse/key files → git (STATUS migrate commit) + core/scene_graph.py, perception/object_localizer.py, perception_grasp.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
