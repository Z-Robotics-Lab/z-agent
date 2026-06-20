# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · GRASP R1 — perception-driven Go2+Piper grasp core LANDED (D17); geometry real-verified
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         sim_tool _start_go2 manip-wiring + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GRASP R1 SHIPPED (D17, commits 19ef11d/b554ab6) — the honest perception→3D-grasp-point core:
         grasp_point_from_rgbd (pure: real depth+mask → camera pointcloud → trimmed centroid → cam→world
         flip; FAILS LOUD, never GT-fallback) + Go2GraspPerception (real d435 RGB-D + lazy VLM/EdgeTAM) +
         PerceptionGraspSkill (detect→segment→point→delegate PickTopDown motion via target_xyz) + sim_tool
         wiring (registered LAST under VECTOR_ENABLE_MANIPULATION). 18 unit tests; spine BYTE-UNCHANGED.
         REAL-SIM: d435 renders the 3 pickables cleanly; geometry proven — green/blue grasp points 3.9/4.1cm
         from GT on REAL depth. (red 180cm = color-prior caught background stool → proves EdgeTAM needed.)
blocked: full VLM bare-cli acceptance ENV-blocked (decision queue, NOT code): timm missing (EdgeTAM dep);
         GPU ~15.2/16GB held by another loop (jepa-ctrl) → moondream3 OOM, serialize; moondream2↔transformers
         5.11 incompat. Run the full acceptance once GPU free + timm installed.
next:    GRASP R2 = (a) full bare-cli "抓前面的东西" once GPU free + timm in: precise EdgeTAM mask → grasp
         point → IK → motion end-to-end; (b) GROUNDED grading-binding — PiperROS2Proxy lacks
         get_object_positions, PiperGripperROS2Proxy lacks weld_is_active, go2_piper.xml has no weld →
         holding_object grades RAN today; add weld + bridge proxy oracle methods (touches Piper proxy
         interface → CEO notification). Alt non-gated: D9 #2 native latency (sync→async).

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
