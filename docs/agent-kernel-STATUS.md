# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · R8 — native verify-compliance fixed + real-verified (D24, steps0→1); grasp Yusen-gated
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         sim_tool _start_go2 manip-wiring + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GRASP R3 SHIPPED (D19, commit 7dd2e38; R1=D17 19ef11d/b554ab6, R2=D18 dc6fa58). The acceptance
         phrase "抓前面的东西" is DEICTIC → resolved WITHOUT a VLM: `perception/front_object.py` picks the
         nearest-shelf most-central vivid-saliency blob (sat_min=140 above the table; 2m workspace; gated out
         the background stool a 'most central' rule first wrongly grabbed). Wired into Go2GraspPerception +
         PerceptionGraspSkill (deictic→front object; named→VLM; VLM-empty→front fallback). REAL-SIM: "前面的
         东西" → center GREEN cylinder, perceived grasp point **6.9cm** from GT (clean 816px single-cylinder
         mask, no VLM/EdgeTAM/network). 11 new unit tests (31 grasp/perception green); spine BYTE-UNCHANGED.
         The depth+mask→3D-point geometry (R1/R2) + the deictic resolver = perception localizes the front
         object end-to-end from real sensor data. IK+motion reuse the proven PickTopDown path (target_xyz).
blocked: VLM识别 + EdgeTAM分割 = pluggable UPGRADE, not on the critical path now (decision queue): timm
         install network-flaky (uv/pypi timeouts) → EdgeTAM pending; moondream2 loads (shim) but boxes
         background on the low-fidelity render; moondream3 13.5GB OOMs. Classical deictic resolver is render-
         tuned (sat_min); a VLM/EdgeTAM front-end would be lighting-robust.
next:    R9 — pick by what's unblocked at cold-ORIENT:
         (A) GRASP [Yusen-gated, D20/D21]: approach (scripted walk, not FAR) + grading-binding (weld +
             bridge→proxy object-state topic, CEO gate). Build when Yusen decides. THE top goal — still
             blocked only on his two calls; everything buildable without them is done + verified.
         (B) ELSE next non-gated North-Star frontier — candidates: (i) native RECOVER on the real model
             (does haiku recover after a FAIL verify? real-LLM turn); (ii) render-fidelity for VLM naming;
             (iii) a milestone REVIEW round (adversarial-verify the native producer's honesty end-to-end on
             the real model now that latency/feedback/verify-compliance shipped). 
         Verified this session: perception 6.9cm (R3), Piper reaches all objects post-approach (R5), native
         latency diagnosed (D22) + live REPL feedback (D23) + verify-compliance (D24) all real-verified.
         Never idle; never cross a gate autonomously.

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
