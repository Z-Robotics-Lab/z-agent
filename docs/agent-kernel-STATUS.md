# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · R17 — GROUNDED grading-binding BUILT (CEO-approved, 782834b); completion (tight reach) escalated to vr-lead (D33)
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         sim_tool _start_go2 manip-wiring + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GROUNDED grading-binding BUILT (R17, D33, commit 782834b) — Yusen approved the weld gate.
         Mirrors the proven SO-101 weld: scene weld eqs injected via the go2_room.xml GRASP_WELDS
         placeholder (scene_room_piper.xml is GENERATED from that template each connect — edit the TEMPLATE);
         MuJoCoPiperGripper._try_grasp/weld_is_active + weld-backed is_holding; MuJoCoPiper.get_object_positions;
         heading-corrected approach + reach_m 0.45->0.25. VERIFIED welds load + _try_grasp fires when the EE
         reaches the object (good run: EE 10.97 reaches green@11.0). 34 unit tests green; spine byte-unchanged.

blocked: GROUNDED grading-binding (CEO gate): the grasp's perception+reach are now real-verified (D32,
         green @ 2.3cm full config), but `is_holding`/`grasped_heuristic` is a no-weld FALSE-NEGATIVE —
         binding a true GROUNDED verdict needs a weld + bridge→proxy object-state topic (Yusen-gated).
         VLM识别 + EdgeTAM分割 = pluggable UPGRADE, off critical path (timm network-flaky; moondream low-fi).
         R15 fix (D32): front_object._open morphological opening severs the table-saturation bridge that
         FUSED the cylinders into one blob — the classical resolver is now topology-robust, not just
         threshold-tuned. A VLM/EdgeTAM front-end would still be more lighting/texture-robust.
next:    R18 — make the grasp RELIABLY complete -> GROUNDED (vr-lead abfbfe3 deep-iterating live). The
         MECHANISM is built; the blocker is TIGHT geometry: Piper reaches ~0.22-0.27m fwd, dog table-limited
         to ~10.6 standoff, cylinders at table-CENTER 11.0 at the edge of reach (near-edge 10.85 -> dog knocks
         them). Fix honestly: robust approach/standoff + reach, or reachable object placement the dog doesn't
         knock (template go2_room.xml), or forward-tilt grasp/forward arm mount. Object must PHYSICALLY lift +
         holding_object grade via the real oracle (NEVER trust skill.success). Then bare-cli "抓前面的东西" ->
         GROUNDED via cli.main. Proven: perception green@2cm (D32), weld mechanism (D33). Spine byte-unchanged.


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
