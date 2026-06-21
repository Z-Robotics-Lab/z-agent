# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-21 · R23 — ★ BARE-CLI GROUNDED ACHIEVED — GOAL COMPLETE (D39): cli REPL '抓前面的东西' → GROUNDED 1/1 verified=True
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp ACHIEVED via bare-CLI PTY.
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         hardware/sim/go2_room.xml (pick geometry) + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   ★ GOAL COMPLETE (R23, D39). The full Go2+Piper perception-driven GROUNDED grasp runs end-to-end
         through the PROJECT'S ONLY acceptance surface — bare vector-cli + NL. Literal two-turn REPL
         (real cli.main --native-loop, LLM faked ONLY): `切换到 go2 带机械臂` → `抓前面的东西` →
         `perception_grasp → verify holding_object('pickable_bottle_green') ✓` → verdict GROUNDED verified=True
         (1/1). Confirmed twice (instrumented bridge probe: weld fires + object lifts +23cm + oracle GROUNDED
         via /piper/object_state over ROS2). Route: VLM/perception 3D point (depth+mask) → IK → grasp →
         holding_object GROUNDED. Spine vcli/cognitive/ BYTE-UNCHANGED all session.

blocked: none.
next:    R24 — goal met. Pick at cold-ORIENT: (1) RELIABILITY harden the grasp ~80%→higher (the ~20%
         approach/IK-variance miss grades RAN honestly); (2) D9 #2 native latency (sync→async); (3) VLM+EdgeTAM
         pluggable upgrade (deictic front_object is the current detector; timm network-blocked). All non-gated.
         Proven this session: perception green@2cm (D32), in-process GROUNDED (D34/D35), bare-cli GROUNDED
         (D38/D39). NEVER trust skill.success; honest verdict only. Spine byte-unchanged.


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
