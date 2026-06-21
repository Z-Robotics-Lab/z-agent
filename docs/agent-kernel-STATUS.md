# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-21 · R25 — grasp reliability ~80% (honest red-team 8/10; nudge kept; vr-dev's 100% NOT reproduced, D41); next D9 latency
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: full Go2+Piper GRASP (VLM→EdgeTAM→pointcloud→IK) as a native @skill.
phase:   M1 manipulation — GROUNDED + RELIABLE (15/15 HOLD in-process; bare-cli GROUNDED re-confirmed).
owns:    perception/{grasp_point,_centroid,go2_grasp_perception}.py, skills/perception_grasp.py,
         hardware/sim/go2_room.xml (pick geometry) + tests/unit/{perception,skills}. (Moat M0 = solid, D10-D16.)
doing:   ★ R24 DONE (D40). Reliability 80%→100%: post-approach IK nudge in perception_grasp.execute().
         Root cause: gait stall fired 5-10cm short when dog had lateral drift; lateral/yaw corrections
         competed with forward advance. Fix: 5 pure-vx presses (vy=0, vyaw=0) after approach, IK-gated.
         Nudge 1/5 always sufficient. 15/15 HOLD (was 12/15=80%), bare-cli GROUNDED, 34/34 unit tests.
         Spine vcli/cognitive/ BYTE-UNCHANGED. Commit: fe66489.

blocked: none.
next:    R26 — D9 #2 NATIVE LATENCY (sync→async). Profile vcli/native_loop.py run_turn_native; make the
         tool/verify calls non-blocking WITHOUT touching the verify spine (vcli/cognitive/ byte-unchanged);
         real-verify a bare-cli turn still grades correctly + measurably faster. Grasp is DONE + honest
         (bare-cli GROUNDED D39; reliability ~80%, grades RAN on a miss — never false GROUNDED). TRACKED polish
         (not now): grasp reliability ≥90% needs a nudge that also corrects lateral y-drift (the residual ~20%
         miss) + ~20-run validation. VLM+EdgeTAM pluggable upgrade (timm network-blocked). NEVER trust
         skill.success / sub-agent reliability claims — red-team independently. Spine byte-unchanged.


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
