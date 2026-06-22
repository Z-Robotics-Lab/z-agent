# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-22 · R35 — cross-MODEL route LANDED (D48) + colour selection now PERCEPTUAL (D49); spine byte-unchanged across 49 decisions
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ started · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M2 cross-model — a learned detector is the first real 2nd model family routed-to + GROUNDED (D48);
         colour selection now PERCEPTUAL via colour-conditioned prompts (D49, 3/3 offset-colour localization).
owns:    perception/grounding_dino.py, perception/detector_capability.py, perception/go2_grasp_perception.py
         (detect→gdino), skills/perception_grasp.py (named→detector routing), worlds/robot.py (register_capabilities).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 48 decisions; engine auto-threads the capability — no spine edit.)
doing:   ★ R34 DONE (D48, commit 70b67e4). Registered IDEA-Research/grounding-dino-tiny as a routable
         Capability(kind=detector); engine auto-wires it to StrategySelector+GoalExecutor (0 cognitive/ edits).
         Grasp's NAMED-query perception now routes to the learned detector (was render-failing moondream);
         deictic→geometry, colour→HSV, named→detector. REAL-VERIFY: in-process 3/3 GROUNDED (grasp_world 2.3cm
         from GT via box+depth not GT, +23cm lift, oracle True, route-fired proven not HSV-fallback); BARE-CLI
         two-turn REPL → verdict GROUNDED verified=True (gdino loads 978/978, picks green). Red-team confirmed
         independently + closed bare-cli (my eyes on the afar boxed frame + the verdict transcript). 37 unit tests.

blocked: none.
next:    R36 — continue deepening cross-MODEL (the chosen axis). D48 caveat 1 CLOSED (D49: colour now perceptual).
         Strong autonomous follow-ons (no gate): (a) route a SECOND capability KIND — wire EdgeTAM as a `segment`
         capability (tighter masks than the box-rect) or YOLOE-seg, so the registry demonstrably holds >1 model
         family routed-to + graded; (b) producer-level routing demo — a (faked-then-live) LLM routes a `detect`
         sub-goal via GoalExecutor._execute_capability (exercise the registry seam at the orchestration layer,
         not only inside the skill), graded by the spine; (c) offset-colour grasp reliability (the existing reach
         limit, diminishing). Gated leaps (CEO): cross-EMBODIMENT (g1 — removed, zero python, large), nav+grasp
         (un-park FAR), explore (TARE), VLN (SysNav), merge→master.
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


## Standing facts (durable)
- **Branch `feat/orchestrator-redesign`** off master; `feat/playground-vln` is ABANDONED (never touch/delete).
- **Honest-verify axis** (the moat's core): a step grades GROUNDED only when a deterministic predicate
  reads an oracle the ACTOR cannot author (actor-causation + structural classifier). The sandbox may only get
  STRICTER (rule 5). vcli/cognitive/ BYTE-UNCHANGED since 7b220d9 (verified 4 ways R34).
- **Cross-MODEL seam (D48):** engine.py builds a CapabilityRegistry, calls world.register_capabilities, threads
  names→StrategySelector + registry→GoalExecutor. A world registers a Capability(kind=chat|detector|planner|vla|…);
  the spine grades it, it never self-certifies. First real entry: the grounding-dino `detect` capability.
- **Acceptance = bare `vector-cli` + NL only** (cli.main PTY asserting the verify VERDICT); `VECTOR_FAKE_LLM`
  fakes ONLY the network LLM. PTY harness needs HF_HOME pinned for the offline detector (D48 note).
- **Native nav routes through the avoidance planner** (D14, `navigate(x,y)`→FAR); `at_position` grades
  UNCAUSED→RAN until actor-causation extends to cmd_vel (honest, spine byte-unchanged).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- Merge/release `feat/orchestrator-redesign` → master.
- cross-EMBODIMENT (g1: removed, zero python — large rebuild) ; nav→FAR + explore→TARE (cmd_vel causation +
  nav-stack colcon bring-up, DQ-15) ; VLN→SysNav venv (DQ-16). New external deps / new-or-changed interfaces /
  hardware / security. Real SO-101 arm acceptance gated on `ls /dev/ttyACM*` (absent — sim only).
