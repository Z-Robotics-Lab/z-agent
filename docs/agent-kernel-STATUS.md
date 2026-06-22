# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-22 · R35 — cross-MODEL route LANDED (D48) + colour selection now PERCEPTUAL (D49); spine byte-unchanged across 49 decisions
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M2 cross-model — a learned detector is the first real 2nd model family, now routed-to BY THE PRODUCER via the
         engine capability-dispatch path (D50), not only inside the grasp skill (D48); colour selection PERCEPTUAL (D49).
owns:    perception/grounding_dino.py, perception/detector_capability.py (now perception-bound), perception/go2_grasp_perception.py
         (detect→gdino), skills/perception_grasp.py (named→detector routing), worlds/robot.py (register_capabilities binds perception).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 50 decisions; engine auto-threads the capability — no spine edit.)
doing:   ★ R36 DONE (D50). Proved the PRODUCER routes a `detect` sub-goal through GoalExecutor._execute_capability to
         REAL grounding-dino (executor_type=capability, strategy="detect", 4 boxes captured in result_data AND on the
         Blackboard), composed into a GROUNDED grasp (holding_object oracle, actor_caused=CAUSED). Clean producer route =
         EMPTY strategy + detect-keyword description (keyword ladder → capability; decomposer leaves empty strategy intact;
         capability names are NOT in KNOWN_STRATEGIES so explicit "detect" would be cleared→invalid). REAL-VERIFY:
         scripts/probe_r36_producer_routes_detect.py on real go2+arm sim + real gdino → PROBE_EXIT=0 PASS
         (/tmp/r36_probe/trace.json). Non-cognitive fix: DetectorCapability now BINDS the agent's perception at
         registration (the kernel hands capability invoke a SkillContext w/ no frame). detect=RAN (read-only, honest),
         grasp=GROUNDED. 128 perception/skills/capability/routing tests green; cognitive diff EMPTY (--stat + --name-status).

blocked: none.
next:    R37 — deepen cross-MODEL / orchestration. Strong autonomous follow-ons (no gate): (a) TRUE box-flow composition —
         add a non-cognitive `box→target_xyz` param to perception_grasp so the routed detect's `${detect.output.boxes}`
         (already on the Blackboard) FLOWS to the grasp via depth back-projection, replacing the grasp's re-perceive
         (producer→consumer composition end-to-end); (b) product-path perception re-bind — rebind the detect capability's
         perception after a mid-session NL sim-start so the routed detector perceives WITHOUT a pre-boot (today
         register_capabilities runs at init_vgg, before the arm boots); (c) route a SECOND capability KIND (EdgeTAM
         `segment` / YOLOE-seg) so the registry holds >1 routed-to+graded model family; (d) live-LLM producer routing
         (drop the faked token stream once a model reliably emits the empty-strategy detect step). Gated leaps (CEO):
         cross-EMBODIMENT (g1), nav+grasp (un-park FAR), explore (TARE), VLN (SysNav), merge→master.
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
