# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · STEP 16 — boolean-necessity closed (D16), real-verified, LANDED crashed-round WIP
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
phase:   M0 honest-foundation — moat hardening (loop-until-dry on the short-circuit/goal-authenticity family).
owns:    vcli/cognitive/** (trace_store, evidence_classifier, actor_causation, coord_goal, verdict) + tests.
doing:   STEP 16 SHIPPED (D16) — 4th adversarial moat review found + closed the BOOLEAN-NECESSITY family:
         the coord gates checked an `at_position(goal)` constant was PRESENT, not NECESSARY, so a CAUSED
         walk to the WRONG place + a verify burying the matching const under `or`/`not`/arithmetic graded
         verified=True. Fix: `_necessary_at_position_consts` (descend `BoolOp(And)` ONLY) →
         `at_position_is_necessary`/`has_necessary_at_position` replace the presence checks in
         `at_position_const_matches`, `coord_goal_mismatch`, `evidence_passed`. Stricter-only (rule 5),
         intra-package, NO CEO gate, world-blind. Real-verified on go2 sim via cli.main PTY (OR-decoy
         `at_position(11,3) or at_position(0,0,1e6)` → RAN/verified False/exit 2, 360s). 78 coord_goal +
         1335 non-sim vcli/unit green (only 3 documented pre-existing deepseek env reds). NOTE: this fix
         was written by a prior round that CRASHED before committing; RE-VERIFIED from scratch + LANDED.
blocked: none.
next:    STEP 17 = 5th adversarial moat review (loop-until-dry): the 4th (STEP 16) found a hole, so the
         family is STILL NOT dry — hunt new bypasses (esp. around necessity gate + multi-coord parse-
         asymmetry residual + object/room goal authenticity) and JUDGE dry. If dry → M0-complete executive
         summary to Yusen (with pending CEO gates). Alt non-gated: D9 #2 latency (native sync→async).

## Standing facts (durable)
- **Branch `feat/orchestrator-redesign`** off master; `feat/playground-vln` is ABANDONED (never touch/delete).
- **Honest-verify axis** (the moat's core): a step grades GROUNDED only when a deterministic predicate
  reads an oracle the ACTOR cannot author (actor-causation + structural classifier), NOT by `is_robot`
  (the old `if is_robot: return True` bypass was deleted in R1) and NOT by sim-vs-real. The sandbox may
  only get STRICTER (rule 5). Detail per decision: D10 recover-fail-closed, D11 membership/causation,
  D12 coord goal-authenticity, D13 callable-container, D15 wrong-predicate-type turn-gate.
- **Acceptance = bare `vector-cli` + NL only** (cli.main PTY asserting the verify VERDICT); never a
  `~/sandbox` harness, never pytest-as-product. `VECTOR_FAKE_LLM` fakes ONLY the network LLM.
- **Cutover LANDED + owner-approved (D9):** the bare-cli REPL runs the native producer by default
  (`VECTOR_REPL_NATIVE=0` = reversible legacy hatch). Native = the design; legacy planner is strangled.
- **Native nav routes through the avoidance planner** (D14, `navigate(x,y)`→FAR); its `at_position`
  grades UNCAUSED→RAN until actor-causation is extended to cmd_vel (honest, spine byte-unchanged).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- Merge/release `feat/orchestrator-redesign` → master.
- nav→FAR + explore→TARE: actor-causation→cmd_vel + nav-stack colcon bring-up (DQ-15).
- VLN→SysNav venv provisioning (DQ-16). New external deps / new-or-changed interfaces / hardware / security.
- Real SO-101 arm acceptance gated on `ls /dev/ttyACM*` (absent — sim only for now).
