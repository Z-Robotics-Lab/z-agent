# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); hidden-bug lessons are
[tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-19
phase:   **M1 STEP 3 COMMITTED + PUSHED (c37c64f on origin/feat/orchestrator-redesign) — native producer SUBSUMES more of the planner's job, ORCHESTRATOR-RE-VERIFIED on the real sim (not a self-report). PURE TEST ADDITION: spine AND native_loop.py BYTE-UNCHANGED (no prompt nudge needed) — 3 new tests only. (A) tests/vcli/test_native_loop_multiskill_pty.py @sim — scripted on a real MuJoCoGo2 via run_turn_native: walk→at_position AND turn→facing, BOTH GROUNDED+CAUSED (a 2nd DISTINCT (skill,predicate); facing IS actor-graded — _BASE_PREDICATES has facing, _base_displacement=max(planar,yaw); the MPC gait UNDER-ROTATES ~half so the script over-commands 180° to face start+90°, the goal not the outcome) → verified True; I re-ran it (19s, PASS). (B) tests/vcli/test_native_loop_multistep_live_pty.py @sim @live_llm (double-gated) — the REAL model decomposes "走到(11,3)再走到(12,3)" into ≥2 walk→at_position legs targeting BOTH coords + ≥1 GROUNDED; I re-ran it: clean 2-leg both-GROUNDED verified True (after 1 transient go2 --sim-go2 sim-boot/bridge flake → retry passed; env-level, NOT moat/logic). (C) tests/vcli/test_native_loop_devworld_pty.py (no sim/key) — REAL FINDING: through real cli.main --native-loop in the DEV world, file_write is an Unknown tool → RAN/exit2 (C.1, leak asserted), BUT run_turn_native dispatches a WRAPPED dev skill → GROUNDED/verified (C.2, producer is world-agnostic). So the gap is WIRING not the producer: cli._init_agent returns None w/o --sim → the native loop offers no dev action tools; the dev "code" toolset (file_write/bash via DEV_TOOL_ALLOWLIST+ToolDispatcher) is the LEGACY planner's tool_call strategy, never surfaced to native. Chunked suite 1197 passed (+2 = C's 2 no-sim tests) + 3 deepseek reds (live tests SKIP w/o opt-in); DELETED NOTHING; no AI attribution. NEXT = STEP 4 = subsume a go2+ARM (Piper) arm/gripper capability through native (arm_at_home/holding_object ARE actor-graded — _ARM_PREDICATES/_GRIPPER_PREDICATES) on the real arm sim: North-Star embodiment breadth + a 3rd distinct capability class. DECISION QUEUE (CEO-gate-adjacent, do NOT cross autonomously): the CUTOVER = make native the DEFAULT turn path + delete the _try_skill_goal_tree/_verify_for_skill fast-path is a cross-package data-flow change → executive summary for Yusen; its prerequisite = close the dev-world wiring leak (surface the dev code toolset as native action tools, flips C.1 leak→covered) so native covers dev too. THEN Phase-2 strangle order (next-prompt.md) → M2 (full NL embodiment switch + TARE/FAR/SysNav/VLA; navigate cmd_vel gated out of actor-causation → honest FAR needs actor-causation extended to cmd_vel first).**
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
- **R1 SHIPPED + pushed (`ae2d0ea` on origin/feat/orchestrator-redesign):** the dishonest `if is_robot: return True`
  evidence-gate bypass is DELETED. `classify_step_evidence` + `verify_oracle_names(agent, engine)` (single-sourced from
  the live verifier namespace, fail-closed) now drive BOTH gates through one AST oracle-vs-tautology classifier
  (`evidence_classifier.classify_verify_expr`): GROUNDED only for a bare predicate-oracle call or a state-oracle-vs-
  constant; RAN for sentinels / no-oracle / tautologies. Robot decompose examples re-keyed onto real predicates;
  fail-closed arm-off-home regression added. **Suite 1134 passed (only the 3 documented deepseek `.env` reds),
  orchestrator-verified green by re-run.** Honest scope LEFT OPEN for R2: the guard is STRUCTURAL — it does NOT verify
  the verify-constant is the real task goal, nor catch shape-trivial state compares (the strict-xfail).
- **R2a SHIPPED = the acceptance INSTRUMENT (built FIRST, per design review wf w39j9p7sj).** The honest verdict
  the engine already computes (`evidence_passed(trace, verify_oracle_names(agent, engine))`) now ESCAPES `cli.main`
  as a machine signal:
  - **PART A** — `cli.py` gains `-p/--print TEXT` (one non-REPL turn) + `--json` (emit one `VECTOR_VERDICT {<json>}`
    stdout line; Rich/banner → stderr). `run_one_turn` runs the turn SYNCHRONOUSLY via `engine.vgg_execute` (never
    `vgg_execute_async`), then builds a frozen `VerdictReport` (`vcli/verdict.py`) ONLY from the EXISTING
    `classify_step_evidence`/`evidence_passed` — never re-derived (contract test
    `test_verdict_report.py::test_verdict_matches_evidence_passed_*`). Exit 0=verified / 2=ran-not-verified /
    1=error|no-trace; harness asserts `verified == (exit==0)`. Shared setup factored into `_build_turn_context`
    (REPL inline copy kept byte-identical; REPL smoke test pins it).
  - **PART B** — `VECTOR_FAKE_LLM=<json>` env seam at the SINGLE `create_backend` site (`create_backend_with_fake_seam`)
    → `tests/harness/fake_backend.py::FakeBackend` returns a canned decompose-plan; replaces ONLY the network LLM
    (real decomposer/validator/skill/GoalVerifier/evidence-gate/verdict still run). A canned `verify='True'` step
    STILL classifies RAN → verified False. Absent env → real `create_backend` unchanged.
  - **PART C** — `tests/harness/pty_cli.py::run_cli_turn` spawns the real entrypoint under a STDLIB `pty` (no pexpect),
    scans for `VECTOR_VERDICT`, asserts the verdict. Cases pinned: no-op staged 'done'→False/exit2,
    GROUNDED dev-world `file_write`+`path_contains`→True/exit0, two-prompt distinct goals (no stale reuse),
    phantom-oracle fail-closed. CI gate: `cli_main`+`capability` markers registered; `tests/conftest.py`
    `pytest_collection_modifyitems` FAILS any `capability` test lacking `@cli_main`; guard asserts `-m cli_main` ≥1.
- **R2b (next) = ACTOR-CAUSATION grading** (revised + honestly reframed by the design review — the "actor-independent
  observer" headline is FALSE for go2 base since SimObserver reads the actor's own MjData; state-level independence
  needs a SECOND shadow MjData = OUT OF SCOPE). Build it THROUGH the R2a PTY harness (prove a teleport/no-op step
  flips `VECTOR_VERDICT.verified` false on the REAL sim). Real SO-101 arm gated on `ls /dev/ttyACM*` (absent now).
3. Pending old-direction gates — recommend: do NOT merge `feat/playground-vln` (cherry-pick only the
   rule-5 GT-leak fix + rule-11 bare-cli fix if needed); DEFER DQ-16 (SysNav venv) / DQ-15 (FAR colcon)
   until a milestone needs them.

## Read order for the redesign session
[../CLAUDE.md](../CLAUDE.md) → North Star → [ARCHITECTURE.md](ARCHITECTURE.md) §1 →
[tricky-bugs.md](tricky-bugs.md) → ADR-006 (kernel/world seam) · ADR-007 (closed loop).
