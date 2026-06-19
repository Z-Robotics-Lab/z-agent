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

## Honest-verify smoking gun (code-verified 2026-06-18, red-team wsmkv96jg)
The evidence gate **short-circuits `if is_robot: return True`** (`trace_store.py:243-244`, `276-277`);
`cli.py:1825` + `engine.py:1801` call it with `is_robot=world.is_robot()`, and the robot world returns
`True` (`robot.py:25`). So **every robot step's verification is auto-passed** — the real reason the old
"verify is the moat" was theatrical on robots (not just sim-anchored, literally `return True`). The real
foolability axis is "does a deterministic predicate read an oracle the ACTOR cannot author," NOT sim-vs-real.
Also: SO-101 NOT connected (`/dev/ttyACM*` empty). M0 must DELETE `is_robot` from the gate first, re-key on
actor-unauthored-snapshot, and use an independent-observer sim grader (red-teamed against no-op/staged snapshots).

## Next (M0 honest foundation — see ~/.vector-nano-loop/campaign.md, hardened by R0 red-team)
- **R1 core SHIPPED (`a738055`, branch feat/orchestrator-redesign):** `vcli/cognitive/evidence_classifier.classify_verify_expr`
  — a pure AST guard, GROUNDED for a bare predicate-oracle call or a state-oracle-vs-constant, RAN for sentinels /
  no-oracle / tautologies (oracle-vs-itself, bare state oracle). 18 passed + 1 strict-xfail (the len-shape gap → R2).
  Honest scope: structural only; goal authenticity deferred to R2. Unused until wired (suite stays green).
- **R1 WIRING (next, per next-prompt.md):** `classify_step_evidence` single-sources BOTH gates; DELETE the
  `is_robot` short-circuits (trace_store.py:243-244 + 276-277); thread oracle_names from the live namespace; re-key
  robot decompose examples onto real predicates (≥1 robot task GROUNDED); flip the 3 intentional tests
  (test_level64_verify_as_eval.py:157/309/374); fail-closed arm-off-home regression; chunked-suite baseline.
- **R2 =** independent-observer sim grader (red-team IT first) + PTY `cli.main` acceptance harness + CI gate.
  Real SO-101 arm gated on `ls /dev/ttyACM*` (absent now), NOT the gold win.
3. Pending old-direction gates — recommend: do NOT merge `feat/playground-vln` (cherry-pick only the
   rule-5 GT-leak fix + rule-11 bare-cli fix if needed); DEFER DQ-16 (SysNav venv) / DQ-15 (FAR colcon)
   until a milestone needs them.

## Read order for the redesign session
[../CLAUDE.md](../CLAUDE.md) → North Star → [ARCHITECTURE.md](ARCHITECTURE.md) §1 →
[tricky-bugs.md](tricky-bugs.md) → ADR-006 (kernel/world seam) · ADR-007 (closed loop).
