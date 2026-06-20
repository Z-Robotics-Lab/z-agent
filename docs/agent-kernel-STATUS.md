# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · GRASP R2 — foreground gating fixes red-can (180→9.5cm) + moondream2 shim (D18)
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         sim_tool _start_go2 manip-wiring + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GRASP R2 SHIPPED (D18, commit dc6fa58; R1 core = D17, commits 19ef11d/b554ab6). R2 hardened the
         geometry + unblocked the VLM model: (1) `_centroid.select_nearest_cluster` = foreground depth-band
         gating in grasp_point (ON by default) → a mask leaking onto same-appearance background localizes the
         FRONT object, not a midpoint. REAL-SIM: the R1 red-can failure 180cm → **9.5cm**; green/blue ~6cm;
         mean 7.1cm (all grasp-viable). (2) vlm.py guarded compat shim (transformers≥5 all_tied_weights_keys)
         → moondream2 now LOADS. 23 grasp unit tests; spine BYTE-UNCHANGED. The depth+mask→3D-point geometry
         is now robust + real-verified end-to-end for ANY mask source.
blocked: full VLM+EdgeTAM bare-cli acceptance (decision queue, NOT code): (a) `timm` install NETWORK-blocked
         (pypi timeouts) → EdgeTAM won't load (now declared in pyproject); (b) VLM 识别 render-fidelity-limited
         — moondream2 boxes the BACKGROUND not the small foreground cylinders on the 320×240 render (design
         risk #2 CONFIRMED, annotated frame inspected); moondream3 is 13.5GB → OOMs the 16GB GPU.
next:    GRASP R3 (frontier) = raise d435 render fidelity (textures/lighting/object framing — the real lever
         for VLM 识别) and/or wire a fitting VLM; install timm + EdgeTAM precise masks once network back; THEN
         GROUNDED grading-binding — PiperROS2Proxy lacks get_object_positions, PiperGripperROS2Proxy lacks
         weld_is_active, go2_piper.xml has no weld → holding_object grades RAN; add weld + bridge proxy oracle
         methods (touches Piper proxy interface → CEO notification). Alt non-gated: D9 #2 native latency.

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
