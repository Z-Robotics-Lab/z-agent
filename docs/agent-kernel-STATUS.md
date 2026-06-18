# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); hidden-bug lessons are
[tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-18
phase:   **DIRECTION REFRAMED BY CEO — redesign being scoped.**
goal:    see CLAUDE.md → North Star (agent-orchestration runtime for physical AI: plan · route to
         the right model/skill · verify each step · recover; sim-first, NL-commanded embodiment
         switch + capability routing TARE/FAR/SysNav/VLA).

## Where we are (2026-06-18)
- **Direction reframed (CEO):** re-assert the orchestration north star — Vector OS schedules
  heterogeneous models + skills + atomic actions across embodiments, and does the 4 things models
  do unreliably (plan / route / verify / recover). It does NOT re-implement nav or manipulation;
  it routes to mature stacks (TARE, FAR planner, SysNav) and policies (VLA / VLM+pointcloud+IK).
- **`feat/playground-vln` is ABANDONED.** It was 163 commits of campaign #2–#12 (bespoke in-MuJoCo
  VLN / photoreal co-sim) and was **never merged to master** (the prior STATUS claim of a
  "merged @ f282180" was false — that commit exists in no branch). `master` (== origin/master,
  `45798a2`) is the clean base.
- **On master already (the keepers):** real SO-101 driver (`hardware/so101/` — Feetech serial, IK,
  gripper, the one honest non-sim oracle), `goal_verifier.py` (263-LOC AST sandbox), kernel/world
  seam, Go2 MuJoCo. Only notable keeper that lived ONLY on the abandoned branch:
  `perception/target_locate.py` (recognise→depth/lidar-locate→navigate sensing) — cherry-pick if needed.

## Honest soft spots the redesign must fix (evidence: prior REDESIGN-BRIEF + 8-agent re-verify)
- Verify "moat" anchored on sim-seeded ground truth → did not transfer to real hardware, and leaked
  to the planner repeatedly. Make it honest by construction: the verify oracle must live where the
  planner physically cannot read it, anchored on state the system does not control (sensors/encoders).
- Product entrypoint barely exercised: only 2 of 347 test files touched `cli.main`; acceptance ran
  through ~55 out-of-repo `~/sandbox` harness scripts (false-greens). Acceptance must drive bare
  `vector-cli` end-to-end (e.g. pexpect/PTY), never a hand-built engine script.
- Accretion to shed: dual ReAct+VGG turn paths, 488-line keyword router, inert learning tier, dead
  isaac/gazebo/pybullet backends, 32 `VECTOR_*` flags, 10 files >800 lines. Mechanism = strangler-fig
  (harness-first, extract the clean core, strangle module-by-module), NOT a from-scratch rewrite.

## Next
1. Scope the redesign spec from the North Star (CEO-gated: spec approval).
2. First honest milestone candidate: bare `vector-cli` NL command on the **real SO-101 arm**, verified
   against Feetech joint encoders (survives removing the sim oracle), driven through `cli.main`.
3. Pending old-direction gates — recommend: do NOT merge `feat/playground-vln` (cherry-pick only the
   rule-5 GT-leak fix + rule-11 bare-cli fix if needed); DEFER DQ-16 (SysNav venv) / DQ-15 (FAR colcon)
   until a milestone needs them.

## Read order for the redesign session
[../CLAUDE.md](../CLAUDE.md) → North Star → [ARCHITECTURE.md](ARCHITECTURE.md) §1 →
[tricky-bugs.md](tricky-bugs.md) → ADR-006 (kernel/world seam) · ADR-007 (closed loop).
