# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-22 · R38 — nav+grasp: FAR un-park CONFIRMED (drives the dog to the table 2/2) but end-to-end GROUNDED NOT landed (honest partial, D52); spine byte-unchanged across 52 decisions
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M2 cross-model — a learned detector is the first real 2nd model family, now routed-to BY THE PRODUCER via the
         engine capability-dispatch path (D50), not only inside the grasp skill (D48); colour selection PERCEPTUAL (D49).
owns:    perception/grounding_dino.py, perception/detector_capability.py (now AGENT-bound, lazy cold-turn rebind),
         perception/go2_grasp_perception.py (detect→gdino), skills/perception_grasp.py (named→detector routing +
         CONSUMES a producer box), worlds/robot.py (register_capabilities binds the agent for the rebind).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 50 decisions; engine auto-threads the capability — no spine edit.)
doing:   R38 DONE — HONEST PARTIAL (D52): nav+grasp cross-skill, Yusen-approved FAR un-park. FAR un-park CONFIRMED as a
         capability: navigate (skills/navigate.py coordinate path → base.navigate_to → FAR) DROVE the dog to the table
         2/2 (5.7m + 4.2m cross-room via /way_point). BUT end-to-end GROUNDED NOT landed: nav_ran 0/2 (FAR stops at its
         0.8m arrival_radius > at_position tolerance → at_position(exact) False → failed-verify, NOT clean RAN — corrected
         the build agent's optimistic "2/2 RAN" via the trace); grasp_GROUNDED 0/2 (from the offset/oblique FAR-arrival
         pose the d435 frames floor/wall → perception mislocalizes the can: trial1 0.87m off at floor, trial2 0.42m off y
         → IK unreachable; frame /tmp/r38_probe/trial2_after.png). Chain COMPOSES (2-step navigate→perception_grasp);
         spine vcli/cognitive/ BYTE-UNCHANGED; NO regression (R37 scripted grasp still GROUNDS). Built (honest WIP,
         committed 47c6591→ceac9da→cf495b9): coordinate navigate (stops+disarms nav flag on arrival), re-pose seam
         (_grasp_ready_repose via approach_pose.py) + fail-loud _perceive_with_scan, deleted th=0.0 fallback. 55 tests green.

blocked: none. KNOWN (spine, do-not-touch): when the grasp flakes (real-pick reach variance) the harness Layer-3
         re-decompose re-emits the grasp with an EMPTY query (param loss on re-plan) → "Nothing localizable for ''".
         This lives in vcli/cognitive/ (harness/decompose) — left untouched per the frozen-spine invariant; first-attempt
         grasp succeeds, so the cold probe re-issues the cold turn up to 3x (each a genuine cold turn) to ride out pick
         variance, not the empty-query bug. Flag for a future spine round (CEO): re-plan should preserve strategy_params.
next:    R39 — CLOSE the nav+grasp end-to-end (D52 residuals, NON-cognitive): (a) precise terminal DOCK — after FAR's
         rough ~0.8m arrival, drive the last leg to the PROVEN head-on grasp standoff on the can's y-line so the d435
         FRAMES the can AND at_position grades RAN (recreate the scripted-from-spawn pose that GROUNDS); (b) perception-
         from-arrival framing robustness. Then bare-cli "去桌子那里把红的拿起来" → nav RAN + grasp GROUNDED end-to-end.
         Other no-gate cross-MODEL: route a 2nd capability KIND (segment); live-LLM producer routing. Gated leaps (CEO,
         queue): re-plan strategy_params-preservation (SPINE — bit nav too, D52), cross-EMBODIMENT (g1), explore (TARE),
         VLN (SysNav), merge→master.
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
