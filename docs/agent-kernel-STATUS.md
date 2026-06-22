# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-22 · R37 — TRUE producer→consumer box-flow composition + cold-turn detector rebind, BOTH GROUNDED; spine byte-unchanged across 50 decisions
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M2 cross-model — a learned detector is the first real 2nd model family, now routed-to BY THE PRODUCER via the
         engine capability-dispatch path (D50), not only inside the grasp skill (D48); colour selection PERCEPTUAL (D49).
owns:    perception/grounding_dino.py, perception/detector_capability.py (now AGENT-bound, lazy cold-turn rebind),
         perception/go2_grasp_perception.py (detect→gdino), skills/perception_grasp.py (named→detector routing +
         CONSUMES a producer box), worlds/robot.py (register_capabilities binds the agent for the rebind).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 50 decisions; engine auto-threads the capability — no spine edit.)
doing:   ★ R37 DONE — both D50 caveats CLOSED, spine byte-unchanged. (A) TRUE producer→consumer box-flow:
         perception_grasp now accepts detections/bbox/boxes from a producer detect step (rule-4 binding
         ${detect_bottle.output.detections}); it COLOUR-SELECTS the matching box and back-projects it via the SAME
         segment + grasp_point_from_rgbd math (consumed_bbox=True, reperceived=False) — its own detect/front_object is
         SUPPRESSED. The grasp's target came FROM the routed detector, not a re-perceive. REAL-VERIFY
         scripts/probe_r37_box_flow_composition.py → real go2+arm + gdino, 4 boxes on Blackboard, grasp GROUNDED
         (holding_object pickable_bottle_green), PROBE_EXIT=0 (/tmp/r37_probe/trace.json). (B) COLD-TURN rebind:
         DetectorCapability now binds the AGENT (not the None-at-init perception snapshot) and pulls agent._perception
         LAZILY at invoke; a capability registered while perception=None still perceives once a mid-session NL sim-start
         restores it (NO re-registration). REAL-VERIFY scripts/probe_r37_cold_turn_rebind.py → cold gap real (snapshot
         None), routed detector perceived (5 boxes) after restore, box consumed, GROUNDED attempt 1, PROBE_EXIT=0
         (/tmp/r37_cold_probe/transcript.json). 50 perception/skills/capability/routing tests green; cognitive diff EMPTY
         (7b220d9..HEAD --stat AND --name-status, + working tree).

blocked: none. KNOWN (spine, do-not-touch): when the grasp flakes (real-pick reach variance) the harness Layer-3
         re-decompose re-emits the grasp with an EMPTY query (param loss on re-plan) → "Nothing localizable for ''".
         This lives in vcli/cognitive/ (harness/decompose) — left untouched per the frozen-spine invariant; first-attempt
         grasp succeeds, so the cold probe re-issues the cold turn up to 3x (each a genuine cold turn) to ride out pick
         variance, not the empty-query bug. Flag for a future spine round (CEO): re-plan should preserve strategy_params.
next:    R38 — deepen cross-MODEL / orchestration. No-gate follow-ons: (a) route a SECOND capability KIND (EdgeTAM
         `segment` / YOLOE-seg) so the registry holds >1 routed-to+graded model family; (b) live-LLM producer routing
         (drop the faked token stream once a model reliably emits the empty-strategy detect step + the
         ${detect.output.detections} binding); (c) make the producer EMIT the box-flow binding itself (today the probe
         authors the ${...} param). Gated leaps (CEO): re-plan param-preservation (spine), cross-EMBODIMENT (g1),
         nav+grasp (un-park FAR), explore (TARE), VLN (SysNav), merge→master.
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
