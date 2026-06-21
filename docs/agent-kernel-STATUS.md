# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-21 · R30 — ★ GRASP+PLACE orchestration BOTH-GROUNDED (red-team reproduced, D46); multi-skill North Star demonstrated
goal:    agent-orchestration runtime for physical AI — plan · route to the right model/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT TOP GOAL: multi-skill GRASP→PLACE orchestration verified GROUNDED through bare cli.main + NL.
phase:   M1 manipulation — orchestration: grasp GROUNDED (D39) + place GROUNDED via placed_count(region) (D46).
owns:    skills/place_top_down.py (verify_hint), skills/utils/place_region.py + tests/skills/{test_place_region,
         test_place_top_down}.py. (Moat M0 solid D10-D16; spine vcli/cognitive/ BYTE-UNCHANGED.)
doing:   ★ R29 DONE (D46). GRASP+PLACE orchestration. ONE NL command "把前面的东西抓起来放到旁边" the native
         producer decomposes into perception_grasp→verify holding_object→place_top_down→verify placed_count→finish.
         Added GROUNDED verify_hint to PlaceTopDownSkill (read by frozen vocab_from_registry via schema —
         spine untouched) + region_around helper. Place target = floor (10.60,2.70,0.05) in the reachable
         central corridor; green rests z~0.04 < _LIFT_MIN_Z=0.10 → placed_count((10.45,2.55,10.75,2.85))==1,
         weld released, is_holding False. BARE-CLI verdict GROUNDED verified=True (2/2 grounded). 114 tests
         green. Commit: bf2accd.

blocked: none.
next:    R31 — manipulation frontier covered: grasp (D39), reliability ~90% (D43), recover (D45), grasp+PLACE
         orchestration (D46, both-GROUNDED, red-team reproduced). Next chunk (autonomous, in-degree):
         ATTRIBUTE GRASP "抓红色的东西" — extend the deictic front_object resolver to attribute/color selection
         (HSV: pick the RED/BLUE/GREEN blob by NL, not just the front one), verify holding_object('pickable_*')
         for the named color; bare-cli GROUNDED. No VLM/timm. The bigger in-KIND leap (nav+grasp cross-skill
         orchestration) needs FAR un-park = a CEO gate (surface, don't cross). VLM+EdgeTAM blocked (timm net).
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
