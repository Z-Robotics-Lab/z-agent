# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-21 · R22 — bare-cli WORLD-ROUTING SOLVED (two-turn REPL→arm-sim oracle); bridge grasp RANs honestly; hold-on-bridge = last gap (D38)
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp ACHIEVED via bare-CLI PTY.
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         hardware/sim/go2_room.xml (pick geometry) + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   BARE-CLI GROUNDED GRASP 3/3 VERIFIED (R19, vr-dev session 2026-06-21).
         Root cause of prior failures found and fixed:
         (1) piper_ros2_proxy._sync_ik_base was using sensor-frame position (+0.3x,+0.2z offset) as body
             position for IK. Fixed: subtract sensor offset before writing to IK model qpos.
         (2) _GRASP_REACH_M=0.25 left dog too far from table; with corrected IK even 0.18m was
             insufficient due to arm-motion backward drift (~0.05m). Fixed: reach_m=0.05 forces stall
             against the pick-table edge, giving the maximum repeatable standoff at body_x~0.50.
         Result: weld fires at 32-47mm (well within 60mm), GROUNDED on all 3 reliability runs.
         Bridge log: "Piper grasp: welded 'pickable_bottle_green' (47mm)" / "(32mm)".
         Perception stack: gp_xyz=(10.857,3.001,0.323) via 320x240 d435 (intrinsics fix R-prev).
         Spine BYTE-UNCHANGED; all edits in skills/ and hardware/sim/.

blocked: none.
next:    R20 — (1) commit the 3 fixed files (piper_ros2_proxy, perception_grasp, sim_tool) to
         feat/orchestrator-redesign. (2) VLM识别 + EdgeTAM分割 = pluggable UPGRADE. (3) D9 #2
         native latency (sync->async). Standing facts: perception green@2cm (D32), GROUNDED grasp
         (D34/D35/R19). NEVER trust skill.success — weld+is_holding+object-lift+oracle are truth.


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
