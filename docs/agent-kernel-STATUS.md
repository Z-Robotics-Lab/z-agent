# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-20 · R18 — Go2+Piper grasp RELIABLY GROUNDED 3/3 on live sim (D34); in-process probe verified
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — perception-driven grasp (the North-Star "VLM + point-cloud + IK" route).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         hardware/sim/go2_room.xml (pick geometry) + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   Go2+Piper grasp RELIABLY GROUNDED (R18, D34). `PerceptionGraspSkill "前面的东西"` -> perceive green ->
         approach (dog jams + tracks y-line) -> weld (EE within 6cm, real reach) -> shoulder-up LIFT. Live
         in-process probe /tmp/grasp_grounded.py: 3/3 (8/8 all runs) GROUNDED — green z 0.32->0.55-0.59
         (~24cm lift), holding_object() AND holding_object('pickable_bottle_green') True via the real oracle.
         Fixes: reach-matched pick geometry (tall pedestal, green at 10.88 = visible+reachable+no-knock);
         skill approach now SEATS the dog to full jam + LATERAL vy y-tracking + shallow pre-grasp + post-weld
         lift. Spine (vcli/cognitive/) BYTE-UNCHANGED. 65 grasp + 17 gripper/oracle unit tests green.

blocked: none for the grasp completion. REMAINING (not blockers): (1) reach the grasp through bare
         `vector-cli` + NL via cli.main PTY (the in-process probe is verified; the CLI path is the
         acceptance-surface follow-up). (2) VLM识别 + EdgeTAM分割 = pluggable UPGRADE off critical path.
next:    R19 — drive the GROUNDED grasp through bare `vector-cli` + NL ("抓前面的东西" -> GROUNDED verdict in
         the REPL conversation via cli.main), then red-team the 3/3 claim. The honest acceptance is the
         oracle reading real physics; the weld fires only from a genuine EE reach (16-44mm measured),
         object physically lifts ~24cm. NEVER trust skill.success.


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
