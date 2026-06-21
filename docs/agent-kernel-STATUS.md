# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · R16 — grasp perception fix RED-TEAM CONFIRMED on live sim (green @2.0cm, was 12.2cm); only GROUNDED weld gate remains
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         sim_tool _start_go2 manip-wiring + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GRASP perception last-mile RESOLVED + RED-TEAM CONFIRMED (R16). Root cause (D32, vr-lead 84ee646)
         = saturation-bridge BLOB FUSION, NOT self-occlusion (a 3-round red herring, R13-R15): the brown
         table's saturation reaches sat_min, so thin table pixel-chains 8-connect cylinders+table into ONE
         blob -> the central green stops being its own component -> a table sliver won. FIX: front_object._open
         morphological opening severs the bridges (topology-robust). I INDEPENDENTLY REPRODUCED on the live
         go2+piper sim (didn't trust the sub-report): full PerceptionGraspSkill "front object" -> grasp_world
         green @ 2.0cm (was 12.2cm; red/blue 15cm), dog approaches, arm reaches over green (11,3). 34
         grasp/perception + regression tests green; spine BYTE-UNCHANGED. The full grasp PERCEIVES ->
         APPROACHES -> REACHES the correct object end-to-end via real perception.

blocked: GROUNDED grading-binding (CEO gate): the grasp's perception+reach are now real-verified (D32,
         green @ 2.3cm full config), but `is_holding`/`grasped_heuristic` is a no-weld FALSE-NEGATIVE —
         binding a true GROUNDED verdict needs a weld + bridge→proxy object-state topic (Yusen-gated).
         VLM识别 + EdgeTAM分割 = pluggable UPGRADE, off critical path (timm network-flaky; moondream low-fi).
         R15 fix (D32): front_object._open morphological opening severs the table-saturation bridge that
         FUSED the cylinders into one blob — the classical resolver is now topology-robust, not just
         threshold-tuned. A VLM/EdgeTAM front-end would still be more lighting/texture-robust.
next:    R17 — the grasp PERCEIVES+APPROACHES+REACHES the correct object end-to-end (R16, green@2cm). The
         ONLY blocker to a VERIFIED grasp is the GROUNDED grading-binding (CEO gate, D20): a weld in
         go2_piper.xml + a bridge->proxy object-state topic so holding_object grades GROUNDED (today is_holding
         is a no-weld FALSE result). Surface to Yusen; do NOT cross. Non-gated cleanup available: drop the
         D31 seg self-filter (get_self_mask) — self-occlusion was a red herring; it adds a per-frame seg
         render for no benefit. Verified this session: perception green@2cm (D32, reproduced R16), approach
         (D28), motion, 4 native pillars (D22-27). Spine byte-unchanged all session.


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
