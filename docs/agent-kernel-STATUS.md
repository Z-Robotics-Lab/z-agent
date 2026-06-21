# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · R19 — bare-cli bridge grading-binding (the non-negotiable acceptance surface) delegated to vr-lead a1a09ae; in-process GROUNDED proven (D35)
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         hardware/sim/go2_room.xml (pick geometry) + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   GROUNDED GRASP WORKS END-TO-END (R18, da78c29 D34 + red-team D35). The GOAL's manipulation route
         is real-verified: PerceptionGraspSkill "前面的东西" -> front_object picks green@2cm -> approach (full
         forward jam + lateral y-track) -> IK -> weld fires at 22-43mm real reach -> green LIFTS +23cm ->
         holding_object() True via the REAL oracle. I RED-TEAMED on the live sim: 4/5 GROUNDED (run3 failed;
         ~80% reliable, NOT the vr-lead's 3/3 — red-team corrected it); /tmp/grasp_run5.png shows green held
         aloft, red+blue on the pedestal. Honest geometry (objects @z=0.32: Piper reach is height-dependent).
         Spine BYTE-UNCHANGED; 34 unit tests green.

blocked: none for the grasp completion. REMAINING (not blockers): (1) reach the grasp through bare
         `vector-cli` + NL via cli.main PTY (the in-process probe is verified; the CLI path is the
         acceptance-surface follow-up). (2) VLM识别 + EdgeTAM分割 = pluggable UPGRADE off critical path.
next:    R19 — finish the grasp to the project's NON-NEGOTIABLE standard: (1) BARE-CLI ACCEPTANCE — drive
         "抓前面的东西" -> GROUNDED through cli.main PTY (verified in-process; the bare vector-cli + NL surface
         is the only acceptance interface, so it's not 100% "done" until this runs). (2) reliability harden
         ~80%->higher (the ~20% approach/IK-variance failure: tighten the standoff/IK so the EE reliably
         reaches). Then D9 #2 native latency (sync->async). Proven: perception green@2cm (D32), GROUNDED grasp
         (D34/D35). NEVER trust skill.success (weld-backed is_holding + object lift + oracle are truth). Spine
         byte-unchanged all session.


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
