# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); hidden-bug lessons are
[tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-19
phase:   **M1+ STRANGLE PROVEN + MOAT HARDENED (2 adversarial-review fixes); CUTOVER PENDING YUSEN (CEO gate). Branch feat/orchestrator-redesign, all pushed. The NATIVE PRODUCER (vcli/native_loop.py `run_turn_native`; honest spine — trace_store/actor_causation/evidence_classifier/verdict — kept BYTE-UNCHANGED except the 2 stricter moat fixes below) subsumes the legacy planner across, all ORCHESTRATOR-RE-VERIFIED on the real cli.main PTY/sim, graded by the moat: go2 (walk live+recover / turn→facing CAUSED / multi-step live) ; arm (pick→holding_object CAUSED via gripper-weld) ; dev (file_write→path_contains, world-agnostic via engine registry code tools) ; cross-language (Chinese cmd → canonical holding_object('banana'), oracle strict). Routing model-driven, no keyword router (rule 1). native-attempt-then-fallback in cli.run_one_turn (--native-first/VECTOR_NATIVE_FIRST default OFF): covered→native, zero-action→legacy. Commit trail: M0 ae2d0ea/eada1bf/bda1047 → M1 d10cfce/a5391eb/c37c64f → step4 arm 1ec2436 → step5 routing ae60b0b → step6 dev ae90386 → step7 i18n 309c4a3 → STEP 8 review HOLE1 d0e7814 + docs abeffc9 → STEP 9 ae22dd5. (per-step detail in journal+git.) MOAT REVIEW (STEP 8 Workflow, 6 adversarial skeptics) found 2 real holes, BOTH FIXED + regression-pinned + real-verified, STRICTER-only (rule 5): HOLE 1 (truthy-constant short-circuit `at_position(99,99) or True` classed GROUNDED) → classify_verify_expr now requires every truth-bearing leaf oracle-gated (d0e7814); the dev/state NO-OP (verify-only `file_exists` with no action classed GROUNDED) → native _grade ties a non-robot predicate's grounding to an action being dispatched (no action → UNCAUSED → R2b downgrade → RAN; ae22dd5, regression C.3 on real cli.main). HOLE 2 (gripper-causation lacks a command conjunct) reproduced NOT-exploitable (objects not at EE at boot) → deferred defense-in-depth. RESIDUAL (deepest, deferred): GOAL-AUTHENTICITY — an action + a trivial-but-true verify (`len(get_position())==3` after a real walk) still grades GROUNDED; needs the real task goal, not a structural check. Suite 1234 + 3 deepseek reds. ===> CUTOVER (native = DEFAULT turn path for covered shapes + staged reversible fast-path→REPL→should_use_vgg→decomposer deletion) = CROSS-PACKAGE DATA-FLOW CEO GATE; EXECUTIVE SUMMARY PRESENTED to Yusen 2026-06-19, AWAITING APPROVAL — never flip default / delete until approved; re-check his response every round (the moat is now stronger than when the summary was written). NEXT (non-gated, while cutover awaits) = STEP 10 a SECOND adversarial moat-review pass (loop-until-dry: confirm HOLE 1 + dev-noop closed, hunt new bypasses, pressure-test the goal-authenticity residual) — if a 2nd pass finds nothing new, the moat is hard + report a holding status. DECISION QUEUE (CEO-gated): CUTOVER (pending Yusen); nav→FAR + explore→TARE need actor-causation→cmd_vel (R2b deferred) + nav-stack colcon DQ-15; VLN→SysNav DQ-16; place needs gripper-release causation; NL embodiment SWITCH needs a 'which-embodiment' predicate; goal-authenticity residual. Real SO-101 arm gated on `ls /dev/ttyACM*` (absent — sim only).**
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
