# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · STEP 15 — wrong-predicate-type closed (D15), real-verified, committed
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
phase:   M0 honest-foundation — moat hardening (loop-until-dry on the short-circuit/goal-authenticity family).
owns:    vcli/cognitive/** (trace_store, evidence_classifier, actor_causation, coord_goal, verdict) + tests.
doing:   STEP 15 SHIPPED (D15) — `evidence_passed` gains a TURN-LEVEL coordinate gate: a go2 coordinate
         goal must be VERIFIED by ≥1 GROUNDED bounded-tol literal `at_position` matching the commanded
         coord; closes the wrong-predicate-type hole (coord goal verified only with `facing()` /
         `len(get_position())==3`). Bonus: `at_position_const` now reads the kwarg form and rejects an
         inflated arrival tol (>2 m). Stricter-only (rule 5), intra-package, NO CEO gate, world-blind
         (dev/arm/answer untouched). Real-verified on go2 sim via cli.main PTY (facing-only-under-coord
         → facing step GROUNDED yet TURN verified False / RAN / exit 2). 53 coord_goal + 708 unit/vcli +
         601 non-sim vcli green (the 3 deepseek + 1 level71 reds are documented pre-existing env reds).
blocked: none.
next:    STEP 16 = 4th adversarial moat review (loop-until-dry): verify STEP-13/14/15 spine changes
         are clean + hunt new bypasses (around the new turn-gate + wrong-predicate-type defaults) and
         JUDGE whether the family is finally dry. If dry → M0-complete executive summary to Yusen
         (with the pending CEO gates) . Alt non-gated: D9 #2 latency (native sync→async, spine byte-unchanged).

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
