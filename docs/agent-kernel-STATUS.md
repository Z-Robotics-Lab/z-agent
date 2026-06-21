# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-21 · R31 — ★ ATTRIBUTE (colour) GRASP — "抓红色的东西/抓蓝色的" grasps the RIGHT-coloured cylinder, GROUNDED (D47); spine byte-unchanged
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: attribute-specified grasp — NL colour selects + grasps the right cylinder, GROUNDED via bare cli.main + NL.
phase:   M1 manipulation — grasp GROUNDED (D39), grasp+PLACE orchestration (D46), ATTRIBUTE/colour grasp (D47).
owns:    perception/front_object.py (parse_color/_hue/_COLOR_HUE/color= kwarg), perception/go2_grasp_perception.py
         (color thread), skills/perception_grasp.py (_COLOR_TO_SCENE verify-label) + tests/unit/{perception/test_front_object,
         skills/test_perception_grasp}.py. (Moat M0 solid D10-D16; spine vcli/cognitive/ BYTE-UNCHANGED.)
doing:   ★ R31 DONE (D47). ATTRIBUTE colour grasp, perception-side ADDITIVE only (spine untouched). NL colour
         ("抓红色的东西"/"抓蓝色的") → front_object_mask keeps only the in-band-hue blobs, picks the most-central
         (FAIL LOUD if no colour match — never the front-most); verify LABEL maps colour→scene name. Grasp POINT
         still perceived from depth+mask. Measured render hues red=2/green=66/blue=111 (cv2 0..180) all in-band → no
         tuning needed. REAL-VERIFY in-process: RED grasp_world 0.028m from red GT (oracle holding_object('pickable_can_red')=True),
         BLUE 0.024m from blue GT (oracle blue=True), GREEN deictic regression unchanged (0.023m, oracle green=True);
         each lifts its own cylinder, others stay down. BARE-CLI: "抓红色的东西" → verify holding_object('pickable_can_red')
         ✓ verdict GROUNDED verified=True; bridge "welded 'pickable_can_red' (51mm)". 44 unit tests green.

blocked: none.
next:    R32 — manipulation frontier broad: grasp (D39), reliability ~90% (D43), recover (D45), grasp+PLACE (D46),
         ATTRIBUTE/colour grasp (D47). HONEST residual: colour SELECTION is reliable (perception correct every run),
         but the BLUE full-grasp is ~50% (2/4) — an EXECUTION reach-limit of the reuse-unchanged approach machinery
         at the most laterally-offset cylinder (y=2.78), not a colour defect; tightening blue's approach/nudge +
         an N-run reliability sweep is the next autonomous chunk. Bigger in-KIND leap (nav+grasp cross-skill) needs
         FAR un-park = a CEO gate (surface, don't cross). VLM+EdgeTAM blocked (timm net).
         Bare vector-cli + NL = ONLY acceptance; spine only ever STRICTER; never trust skill.success/sub-claims.


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
